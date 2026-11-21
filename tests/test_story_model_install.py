from email.message import Message
from hashlib import sha256
from http.client import IncompleteRead
from io import BytesIO
from urllib.error import HTTPError

import pytest

from candidates import story_model_install as installer


_MODEL = b"portable fixture"
_TOKENIZER = b"tokenizer fixture"
_ARTIFACTS = {"onnx/model.onnx": _MODEL, "onnx/tokenizer.json": _TOKENIZER}
_PREFIX = f"https://huggingface.co/{installer.MODEL_ID}/resolve/{installer.REVISION}/"


class Response(BytesIO):
    status = 200

    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}


class FakeOpener:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        assert 0 < timeout <= installer.SOCKET_TIMEOUT_SECONDS
        reply = self.responses[request.full_url]
        if isinstance(reply, Exception):
            raise reply
        return reply


def _redirect(before, after):
    headers = Message()
    headers["Location"] = after
    return HTTPError(before, 302, "Redirect", headers, BytesIO())


@pytest.fixture
def fake_download(monkeypatch):
    monkeypatch.setattr(installer, "PORTABLE_FILES", {k: sha256(v).hexdigest() for k, v in _ARTIFACTS.items()})
    opener = FakeOpener({_PREFIX + k: Response(v) for k, v in _ARTIFACTS.items()})
    monkeypatch.setattr(installer, "build_opener", lambda _: opener)
    return opener


def test_install_publishes_complete_pinned_set_and_reuses_without_network(tmp_path, fake_download):
    destination = installer.profile_story_model_destination(tmp_path)
    calls = []

    def progress(done, total):
        calls.append((done, total))
        if done != total:
            assert not destination.exists()

    assert not destination.parent.exists()
    assert installer.install_story_model(destination, on_progress=progress) == destination
    assert {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()} == set(_ARTIFACTS)
    assert {k: (destination / k).read_bytes() for k in _ARTIFACTS} == _ARTIFACTS
    assert calls[-1] == (len(_MODEL) + len(_TOKENIZER),) * 2
    assert installer.install_story_model(destination) == destination
    assert [r.full_url for r in fake_download.requests] == [_PREFIX + name for name in _ARTIFACTS]
    assert all(r.get_header("Authorization") is None and r.get_header("Cookie") is None for r in fake_download.requests)
    assert set(destination.parent.iterdir()) == {destination}


def test_install_preserves_existing_invalid_directory_without_network(tmp_path, fake_download):
    destination = tmp_path / "model"
    destination.mkdir()
    personal = destination / "personal.txt"
    personal.write_bytes(b"do not move")
    with pytest.raises(installer.StoryModelInstallError, match="not changed"):
        installer.install_story_model(destination)
    assert personal.read_bytes() == b"do not move"
    assert not fake_download.requests


@pytest.mark.parametrize("url", [
    "http://huggingface.co/bad",
    "http://us.aws.cdn.hf.co/bad",
    "https://us.aws.cdn.hf.co.example.net/bad",
    "https://unknown.cdn.hf.co/bad",
    "https://huggingface.co.example.net/bad",
    "https://user:password@cas-bridge.xethub.hf.co/bad",
    "https://cas-bridge.xethub.hf.co:8443/bad",
    "https://161.0.0.1/bad",
])
def test_model_rejects_unapproved_redirects(tmp_path, fake_download, url):
    first = _PREFIX + "onnx/model.onnx"
    fake_download.responses[first] = _redirect(first, url)
    with pytest.raises(installer.StoryModelInstallError, match="Unapproved"):
        installer.install_story_model(tmp_path / "model")
    assert [r.full_url for r in fake_download.requests] == [first]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("host", ["cas-bridge.xethub.hf.co", "us.aws.cdn.hf.co"])
def test_model_follows_approved_cdn_without_forwarding_sensitive_headers(tmp_path, fake_download, host):
    first = _PREFIX + "onnx/model.onnx"
    cdn = f"https://{host}/xet-bridge/some-file?temporary-signature"
    fake_download.responses[first] = _redirect(first, cdn)
    fake_download.responses[cdn] = Response(_MODEL)
    installer.install_story_model(tmp_path / "model")
    assert [r.full_url for r in fake_download.requests] == [first, cdn, _PREFIX + "onnx/tokenizer.json"]
    assert all(r.get_header("Authorization") is None and r.get_header("Cookie") is None
               and r.get_header("Referer") is None for r in fake_download.requests)


def test_model_checksum_failure_never_leaves_partial_install(tmp_path, fake_download):
    fake_download.responses[_PREFIX + "onnx/tokenizer.json"] = Response(b"tampered")
    with pytest.raises(installer.StoryModelInstallError, match="Checksum mismatch"):
        installer.install_story_model(tmp_path / "model")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("with_header", [False, True])
def test_model_enforces_cumulative_limit_even_without_length(monkeypatch, tmp_path, fake_download, with_header):
    monkeypatch.setattr(installer, "DOWNLOAD_BYTE_LIMIT", len(_MODEL) + len(_TOKENIZER) - 1)
    if with_header:
        fake_download.responses[_PREFIX + "onnx/tokenizer.json"] = Response(
            _TOKENIZER, {"Content-Length": str(len(_TOKENIZER))}
        )
    with pytest.raises(installer.StoryModelInstallError, match="size limit"):
        installer.install_story_model(tmp_path / "model")
    assert list(tmp_path.iterdir()) == []


def test_model_cancellation_cleans_staging_without_publishing(tmp_path, fake_download):
    cancelled = False

    def progress(_done, _total):
        nonlocal cancelled
        cancelled = True

    with pytest.raises(installer.StoryModelInstallCancelled):
        installer.install_story_model(tmp_path / "model", cancelled=lambda: cancelled, on_progress=progress)
    assert len(fake_download.requests) == 1
    assert list(tmp_path.iterdir()) == []


def test_model_network_error_hides_signed_urls_and_cleans_staging(tmp_path, fake_download):
    first = _PREFIX + "onnx/model.onnx"
    cdn = "https://cas-bridge.xethub.hf.co/xet-bridge/data?secret-signature"
    fake_download.responses[first] = _redirect(first, cdn)
    fake_download.responses[cdn] = HTTPError(cdn, 403, "Forbidden", Message(), BytesIO())
    with pytest.raises(installer.StoryModelInstallError, match="HTTP 403") as error:
        installer.install_story_model(tmp_path / "model")
    assert "secret-signature" not in str(error.value)
    assert list(tmp_path.iterdir()) == []


def test_model_rejects_broken_transfer(tmp_path, fake_download):
    class ShortResponse(Response):
        def read1(self, _):
            raise IncompleteRead(b"partial", 200)

    fake_download.responses[_PREFIX + "onnx/model.onnx"] = ShortResponse(b"")
    with pytest.raises(installer.StoryModelInstallError):
        installer.install_story_model(tmp_path / "model")
    assert list(tmp_path.iterdir()) == []


def test_model_cancels_before_any_network_or_storage(tmp_path, fake_download):
    destination = tmp_path / "not-created" / "model"
    with pytest.raises(installer.StoryModelInstallCancelled):
        installer.install_story_model(destination, cancelled=lambda: True)
    assert not fake_download.requests and not destination.parent.exists()


def test_model_stops_on_overall_deadline(tmp_path, fake_download, monkeypatch):
    now = 0

    def clock():
        return now

    def advance_clock(_done, _total):
        nonlocal now
        now = installer.TOTAL_TIMEOUT_SECONDS + 1

    monkeypatch.setattr(installer, "monotonic", clock)
    with pytest.raises(installer.StoryModelInstallError, match="timed out"):
        installer.install_story_model(tmp_path / "model", on_progress=advance_clock)
    assert len(fake_download.requests) == 1
    assert list(tmp_path.iterdir()) == []


def test_model_reuses_concurrently_published_copy(tmp_path, fake_download):
    destination = tmp_path / "model"

    def publish_other_instance(done, total):
        if done == total or destination.exists():
            return
        (destination / "onnx").mkdir(parents=True)
        for key, value in _ARTIFACTS.items():
            (destination / key).write_bytes(value)
        (destination / "other-instance").write_text("keep")

    assert installer.install_story_model(destination, on_progress=publish_other_instance) == destination
    assert (destination / "other-instance").read_text() == "keep"
    assert set(tmp_path.iterdir()) == {destination}


def test_explicit_repair_preserves_base_and_reuses_verified_alternate(tmp_path, fake_download):
    base = installer.profile_story_model_destination(tmp_path)
    base.mkdir(parents=True)
    (base / "original.txt").write_bytes(b"keep")
    alternate = installer.profile_story_model_repair_destination(tmp_path)
    assert alternate.parent == base.parent and alternate != base
    assert installer.repair_profile_story_model(tmp_path) == alternate
    for name, data in _ARTIFACTS.items():
        assert (alternate / name).read_bytes() == data
    request_count = len(fake_download.requests)
    assert installer.repair_profile_story_model(tmp_path) == alternate
    assert len(fake_download.requests) == request_count
    assert list(base.iterdir()) == [base / "original.txt"]
    assert (base / "original.txt").read_bytes() == b"keep"


@pytest.mark.parametrize("cancel_after_download", [False, True])
def test_failed_repair_never_adopts_or_changes_original(tmp_path, fake_download, cancel_after_download):
    base = installer.profile_story_model_destination(tmp_path)
    base.mkdir(parents=True)
    (base / "original.txt").write_text("keep")
    alternate = installer.profile_story_model_repair_destination(tmp_path)
    if cancel_after_download:
        with pytest.raises(installer.StoryModelInstallCancelled):
            installer.repair_profile_story_model(tmp_path, cancelled=lambda: alternate.exists())
    else:
        fake_download.responses[_PREFIX + "onnx/tokenizer.json"] = Response(b"tampered")
        with pytest.raises(installer.StoryModelInstallError) as exc:
            installer.repair_profile_story_model(tmp_path)
        assert exc.value.code == "integrity"
    assert (base / "original.txt").read_text() == "keep"
    assert set(base.parent.iterdir()) == {base}


def test_repair_does_not_replace_concurrently_created_empty_folder(tmp_path, fake_download):
    alternate = installer.profile_story_model_repair_destination(tmp_path)

    def create_other_slot(_done, _limit):
        alternate.mkdir(exist_ok=True)

    with pytest.raises(installer.StoryModelInstallError) as exc:
        installer.repair_profile_story_model(tmp_path, on_progress=create_other_slot)
    assert exc.value.code == "existing_invalid"
    assert alternate.is_dir() and not list(alternate.iterdir())
    assert len(fake_download.requests) == len(_ARTIFACTS)
    fake_download.responses.update({_PREFIX + name: Response(data) for name, data in _ARTIFACTS.items()})
    assert installer.repair_profile_story_model(tmp_path) == alternate.with_name(alternate.name + "-2")
    assert alternate.is_dir() and not list(alternate.iterdir())


def test_repair_reuses_verified_later_slot_and_stops_when_all_occupied(tmp_path, fake_download):
    first = installer.profile_story_model_repair_destination(tmp_path)
    second = first.with_name(first.name + "-2")
    second.mkdir(parents=True)
    (second / "untouched").write_text("keep")
    third = first.with_name(first.name + "-3")
    installer.install_story_model(third)
    count = len(fake_download.requests)
    assert installer.repair_profile_story_model(tmp_path) == third
    assert not first.exists()
    assert len(fake_download.requests) == count
    (third / "onnx" / "tokenizer.json").unlink()
    first.mkdir()
    with pytest.raises(installer.StoryModelInstallError) as exc:
        installer.repair_profile_story_model(tmp_path)
    assert exc.value.code == "existing_invalid"
    assert len(fake_download.requests) == count
    assert (second / "untouched").read_text() == "keep"


def test_repair_does_not_follow_redirected_managed_cache(tmp_path, fake_download):
    custom = tmp_path / "custom"
    custom.mkdir()
    profile = tmp_path / "profile"
    profile.mkdir()
    try:
        (profile / "cache").symlink_to(custom, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(installer.StoryModelInstallError) as exc:
        installer.repair_profile_story_model(profile)
    assert exc.value.code == "existing_invalid"
    assert not list(custom.iterdir())
    assert not fake_download.requests


def test_repair_falls_back_to_exclusive_copy_if_hardlinks_unavailable(tmp_path, fake_download, monkeypatch):
    def unsupported(*_args):
        raise OSError("hardlinks unavailable")

    monkeypatch.setattr(installer, "link", unsupported)
    alternate = installer.repair_profile_story_model(tmp_path)
    assert {name: (alternate / name).read_bytes() for name in _ARTIFACTS} == _ARTIFACTS


@pytest.mark.parametrize("timeout_type", ["open", "wrapped", "read", "deadline_during_read"])
def test_model_distinguishes_idle_transport_from_total_deadline(tmp_path, fake_download, monkeypatch, timeout_type):
    from urllib.error import URLError

    t = [0.0]
    monkeypatch.setattr(installer, "monotonic", lambda: t[0])
    first = _PREFIX + "onnx/model.onnx"

    class InterruptAfterBytes(Response):
        def read1(self, length):
            if self.tell() > 0:
                if timeout_type == "deadline_during_read":
                    t[0] = installer.TOTAL_TIMEOUT_SECONDS
                raise TimeoutError("private transfer address")
            return super().read1(length)

    if timeout_type == "open":
        fail = TimeoutError("private transfer address")
    elif timeout_type == "wrapped":
        fail = URLError(TimeoutError("private transfer address"))
    else:
        fail = InterruptAfterBytes(_MODEL)
    fake_download.responses[first] = fail
    destination = tmp_path / "model"
    progress = []
    with pytest.raises(installer.StoryModelInstallError) as got:
        installer.install_story_model(destination, on_progress=lambda done, total: progress.append(done))
    assert got.value.code == ("timeout" if timeout_type == "deadline_during_read" else "idle_timeout")
    assert "private" not in str(got.value)
    assert bool(progress) == timeout_type.endswith("read")
    assert not destination.exists() and list(tmp_path.iterdir()) == []

    fake_download.responses[first] = Response(_MODEL)
    assert installer.install_story_model(destination) == destination
    assert (destination / "onnx/model.onnx").read_bytes() == _MODEL

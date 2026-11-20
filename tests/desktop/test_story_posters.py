import pytest
from PyQt6.QtCore import QObject, pyqtSignal, QByteArray, QSize
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtNetwork import QNetworkRequest, QNetworkReply
from desktop.shared import story_posters as p

URL='https://image.tmdb.org/t/p/w342/test.jpg'

@pytest.mark.parametrize('url', ['http://image.tmdb.org/t/p/w342/test.jpg','https://evil.test/a.jpg','https://image.tmdb.org.evil.test/t/p/w342/a.jpg','https://image.tmdb.org/t/p/w342/a.jpg?token=x','https://image.tmdb.org/t/p/w342/../a.jpg','https://user@image.tmdb.org/t/p/w342/a.jpg','https://image.tmdb.org:443/t/p/w342/a.jpg','https://image.tmdb.org/t/p/w342/a.svg','https://image.tmdb.org/t/p/w342/a.jpg#x'])
def test_reject_non_canonical_urls(url):
    assert p.cdn_url(url) is None

class Reply(QObject):
    readyRead=pyqtSignal();finished=pyqtSignal()
    def __init__(self,data=b'',status=200,error=QNetworkReply.NetworkError.NoError):
        super().__init__();self.data=data;self.status=status;self.err=error;self.aborted=False
    def setReadBufferSize(self,n):self.limit=n
    def bytesAvailable(self):return len(self.data)
    def readAll(self):return QByteArray(self.data)
    def attribute(self,a):return self.status
    def error(self):return self.err
    def errorString(self):return 'mock offline'
    def abort(self):
        self.aborted=True;self.err=QNetworkReply.NetworkError.OperationCanceledError;self.finished.emit()

@pytest.fixture
def setup(qapp,monkeypatch,tmp_path):
    import posters.download_images as downloads
    monkeypatch.setattr(downloads,'PREVIEW_POSTER_DIR',tmp_path)
    c=p.DirectPosterController();requests=[];replies=[]
    def get(request):
        requests.append(request);r=Reply();replies.append(r);return r
    monkeypatch.setattr(c._manager,'get',get)
    return c,requests,replies

def test_bounded_requests_headers_cancel_and_late_response(setup):
    c,requests,replies=setup
    for i in range(8):c.enqueue(str(i),URL.replace('test',str(i)))
    assert len(requests)==2 and len(c._queue)==6
    r=requests[0]
    assert r.url().host()=='image.tmdb.org'
    assert r.attribute(QNetworkRequest.Attribute.RedirectPolicyAttribute)==QNetworkRequest.RedirectPolicy.ManualRedirectPolicy
    assert r.attribute(QNetworkRequest.Attribute.CookieLoadControlAttribute)==QNetworkRequest.LoadControl.Manual
    assert set(bytes(h).lower() for h in r.rawHeaderList())=={b'accept'}
    events=[];c.poster_ready.connect(lambda *x:events.append(x));c.cancel_pending()
    assert all(r.aborted for r in replies) and not c._active and not c._queue and not events
    c.enqueue('new',URL.replace('test','0'));assert len(requests)==3

@pytest.mark.parametrize('status,data',[(302,b'redirect'),(200,b'broken'),(200,b'x'*(p.MAX_POSTER_BYTES+1)),(404,b'missing')])
def test_bad_response_keeps_placeholder(setup,status,data):
    c,requests,replies=setup;events=[];c.poster_ready.connect(lambda *x:events.append(x));c.enqueue('one',URL)
    r=replies[0];r.status=status;r.data=data;r.readyRead.emit()
    if not r.aborted:r.finished.emit()
    assert not events and not p.preview_poster_path_for_url(URL).exists()

def test_success_cache_reuse_and_pixels(setup,tmp_path):
    c,requests,replies=setup
    source=tmp_path/'source.png';img=QImage(30,45,QImage.Format.Format_RGB32);img.fill(0xffaa55);assert img.save(str(source))
    c.enqueue('one',URL);replies[0].data=source.read_bytes();replies[0].finished.emit()
    assert p.local_picture(p.preview_poster_path_for_url(URL),QSize(68,94)) is not None
    c.enqueue('two',URL);assert len(requests)==1
    bomb=tmp_path/'large.png';large=QImage(4097,1,QImage.Format.Format_RGB32);large.fill(1);large.save(str(bomb))
    assert p.local_picture(bomb,QSize(68,94)) is None

def test_generation_deleted_label_bad_cache_and_view_limit(qtbot,monkeypatch,tmp_path):
    import posters.download_images as downloads
    monkeypatch.setattr(downloads,'PREVIEW_POSTER_DIR',tmp_path)
    widget=QWidget();qtbot.addWidget(widget);widget.show();binder=p.CardPosters(widget)
    monkeypatch.setattr(binder.controller,'_pump',lambda:None)
    p.preview_poster_path_for_url(URL).write_bytes(b'broken')
    labels=[]
    for i in range(45):
        label=QLabel('placeholder',widget);label.resize(68,94);labels.append(label)
        binder.bind(label,{'poster_url':URL},'fixture')
    assert len(binder.labels)==45 and not p.preview_poster_path_for_url(URL).exists()
    old=next(iter(binder.labels));binder.clear();binder._ready(old,'missing')
    qtbot.wait(5);assert not binder.controller._queue
    assert labels[0].text()=='placeholder'

def test_saved_and_watched_keep_poster_metadata(qtbot,monkeypatch):
    from candidates import service
    from desktop.shell.main_window import WatchedMoviesWindow
    candidate={'title':'Poster fixture','year':2025,'tmdb_id':994501,'media_type':'movie','overview':'Авторский тест','poster_url':URL,'poster_path':'/test.jpg'}
    service.add_candidate_to_watchlist(candidate)
    window=WatchedMoviesWindow();qtbot.addWidget(window)
    view=window._tab_registry._specs['watched'].view
    captured=[];monkeypatch.setattr(view.posters,'bind',lambda label,record,title:captured.append(record))
    view.reload_entries();assert p.cdn_url(__import__('posters.cache',fromlist=['extract_existing_poster_info']).extract_existing_poster_info(captured[-1]).get('poster_url'))==URL
    service.mark_story_watched(candidate);view._switch_section('watched')
    assert p.cdn_url(__import__('posters.cache',fromlist=['extract_existing_poster_info']).extract_existing_poster_info(captured[-1]).get('poster_url'))==URL
    window.shutdown_background_workers()


def test_offscreen_cards_wait_for_scroll_and_hidden_view_cancels(qtbot,monkeypatch,tmp_path):
    from PyQt6.QtWidgets import QScrollArea,QVBoxLayout
    import posters.download_images as downloads
    monkeypatch.setattr(downloads,'PREVIEW_POSTER_DIR',tmp_path)
    root=QWidget();root.resize(180,180);qtbot.addWidget(root);layout=QVBoxLayout(root)
    scroll=QScrollArea();scroll.setWidgetResizable(True);layout.addWidget(scroll)
    body=QWidget();rows=QVBoxLayout(body);scroll.setWidget(body)
    binder=p.CardPosters(root);sent=[];replies=[]
    def get(request):
        sent.append(request.url().toString());reply=Reply();replies.append(reply);return reply
    monkeypatch.setattr(binder.controller._manager,'get',get)
    for i in range(5):
        label=QLabel(str(i));label.setFixedSize(68,94);rows.addWidget(label)
        binder.bind(label,{'poster_url':URL.replace('test',str(i))},str(i))
    root.show();qtbot.wait(20);binder._visible()
    assert 1<=len(sent)<=2
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    for reply in list(replies):reply.finished.emit()
    qtbot.wait(20);binder._visible()
    assert any('/4.jpg' in url for url in sent)
    root.hide();assert not binder.controller._active and not binder.controller._queue
    root.close();binder.clear()


def test_offline_cooldown_and_atomic_write_failure(setup,monkeypatch,tmp_path):
    c,requests,replies=setup
    c.enqueue('one',URL);replies[0].err=QNetworkReply.NetworkError.HostNotFoundError;replies[0].finished.emit()
    c.enqueue('again',URL);assert len(requests)==1
    assert c._failed_at and c._unavailable_hosts
    from pathlib import Path
    monkeypatch.setattr(Path,'replace',lambda *a: (_ for _ in ()).throw(OSError('disk full')))
    assert c._write_preview(URL,b'fixture') is None
    assert list(tmp_path.iterdir())==[]

def test_scrolling_prunes_waiting_offscreen_downloads(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QScrollArea, QVBoxLayout
    import posters.download_images as downloads

    monkeypatch.setattr(downloads, 'PREVIEW_POSTER_DIR', tmp_path)
    root = QWidget()
    qtbot.addWidget(root)
    root.resize(250, 410)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    QVBoxLayout(root).addWidget(scroll)
    body = QWidget()
    rows = QVBoxLayout(body)
    scroll.setWidget(body)
    binder = p.CardPosters(root)
    requests, replies = [], []

    def get(request):
        requests.append(request.url().fileName())
        reply = Reply()
        replies.append(reply)
        return reply

    monkeypatch.setattr(binder.controller._manager, 'get', get)
    for i in range(12):
        label = QLabel(str(i))
        label.setFixedSize(68, 94)
        rows.addWidget(label)
        binder.bind(label, {'poster_url': URL.replace('test', str(i))}, str(i))
    root.show()
    qtbot.waitUntil(lambda: len(requests) == 2)
    assert binder.controller._queue
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    binder._visible()
    replies[0].finished.emit()
    assert requests[:2] == ['0.jpg', '1.jpg']
    assert int(requests[2].split('.')[0]) >= 8
    root.hide()

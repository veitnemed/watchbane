"""Profile-local, disposable passage vectors. Fixed binary records, never pickle.

Files contain hashes and 384 little-endian float32 values, not source text. Each
record is independently atomic; interrupted writes cannot invalidate other rows.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

PREPROCESS_VERSION = 'e5-passage-v1-prefix-mask-mean-l2-512'
MAGIC = b'WBVEC01\0'
DIMENSION = 384
RECORD_SIZE = len(MAGIC) + 32 + DIMENSION * 4 + 32


def model_identity(files, runtime_version):
    return json.dumps({'artifacts': files, 'runtime': runtime_version,
                       'provider': 'CPUExecutionProvider'}, sort_keys=True, separators=(',', ':'))


class PassageVectorCache:
    def __init__(self, profile_dir, identity, preprocessing=PREPROCESS_VERSION):
        namespace = sha256((identity + '\0' + preprocessing).encode('utf-8')).hexdigest()
        self.namespace = namespace
        self.root = Path(profile_dir) / 'story_vectors_v1' / namespace
        self.hits = self.misses = self.errors = self.writes = 0

    def key(self, text):
        return sha256((self.namespace + '\0passage: ' + text).encode('utf-8')).hexdigest()

    def path(self, text):
        return self.root / (self.key(text) + '.vec')

    def load(self, text):
        import numpy as np
        key = self.key(text)
        path = self.path(text)
        try:
            if path.is_symlink() or self.root.is_symlink() or self.root.parent.is_symlink():
                raise ValueError('Symlink cache is not accepted')
            with path.open('rb') as stream:
                raw = stream.read(RECORD_SIZE + 1)
            if len(raw) != RECORD_SIZE or raw[:8] != MAGIC or raw[8:40] != bytes.fromhex(key):
                raise ValueError('Invalid record header or length')
            if sha256(raw[:-32]).digest() != raw[-32:]:
                raise ValueError('Invalid record checksum')
            vector = np.frombuffer(raw[40:-32], dtype='<f4').copy()
            if not np.isfinite(vector).all() or abs(float(np.linalg.norm(vector)) - 1.0) > .001:
                raise ValueError('Invalid normalized vector')
            self.hits += 1
            return vector
        except FileNotFoundError:
            self.misses += 1
        except (OSError, ValueError):
            self.errors += 1
            self.misses += 1
        return None

    def save(self, text, vector):
        import numpy as np
        temp = None
        try:
            values = np.asarray(vector, dtype='<f4')
            if values.shape != (DIMENSION,) or not np.isfinite(values).all() or abs(float(np.linalg.norm(values)) - 1.0) > .001:
                raise ValueError('Invalid normalized vector')
            if self.root.parent.is_symlink() or self.root.is_symlink():
                raise ValueError('Symlink cache is not accepted')
            self.root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.root.mkdir(mode=0o700, exist_ok=True)
            raw = MAGIC + bytes.fromhex(self.key(text)) + values.tobytes()
            raw += sha256(raw).digest()
            fd, temp = tempfile.mkstemp(prefix='.vector-', suffix='.tmp', dir=self.root)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path(text))
            self.writes += 1
        except (OSError, ValueError):
            # Disk full/read-only/corrupt cache must not prevent live retrieval.
            self.errors += 1
        finally:
            if temp is not None:
                try: Path(temp).unlink(missing_ok=True)
                except OSError: pass


class CachedPassageEncoder:
    """Only passage embeddings persist; queries always use the original encoder."""
    def __init__(self, encoder, profile_dir):
        self.encoder = encoder
        self.np = encoder.np
        self.variant = encoder.variant
        self.cache = PassageVectorCache(profile_dir, encoder.cache_identity)

    def encode(self, texts, prefix='passage: ', cancelled=None):
        if prefix != 'passage: ':
            return self.encoder.encode(texts, prefix=prefix, **({'cancelled': cancelled} if cancelled else {}))
        texts = list(texts)
        if not texts:
            return self.np.empty((0, DIMENSION), dtype=self.np.float32)
        vectors = {}
        missing = []
        for text in dict.fromkeys(texts):
            if cancelled and cancelled(): raise InterruptedError('Story indexing cancelled')
            vector = self.cache.load(text)
            if vector is None: missing.append(text)
            else: vectors[text] = vector
        if missing:
            computed = self.encoder.encode(missing, **({'cancelled': cancelled} if cancelled else {}))
            for text, vector in zip(missing, computed):
                if cancelled and cancelled(): raise InterruptedError('Story indexing cancelled')
                vectors[text] = vector
                self.cache.save(text, vector)
        return self.np.stack([vectors[text] for text in texts])

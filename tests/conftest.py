"""
Ortak test yapılandırması — tüm test dosyaları aynı izole DB'yi kullanır.
Bu dosya pytest tarafından otomatik olarak yüklenir.
"""
import os
import tempfile

_DATA_ROOT = tempfile.TemporaryDirectory(prefix="oms_test_shared_")
os.environ["LOCALAPPDATA"] = _DATA_ROOT.name

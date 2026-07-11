import pytest

from zpl2usb.jobs import JobSplitter, split_jobs


def test_single_job():
    data = b"^XA^FO10,10^FDhi^FS^XZ"
    assert split_jobs(data) == [data]


def test_multiple_jobs_one_chunk():
    a = b"^XA^FDone^XZ"
    b = b"^XA^FDtwo^XZ"
    assert split_jobs(a + b) == [a, b]


def test_jobs_with_noise_between():
    a = b"^XA^FDone^XZ"
    b = b"^XA^FDtwo^XZ"
    # newlines / whitespace between jobs are dropped
    assert split_jobs(a + b"\r\n\r\n" + b) == [a, b]


def test_leading_noise_dropped():
    a = b"^XA^FDone^XZ"
    assert split_jobs(b"garbage\n" + a) == [a]


def test_incomplete_job_buffered():
    s = JobSplitter()
    assert s.feed(b"^XA^FDpart") == []
    assert s.feed(b"ial^XZ") == [b"^XA^FDpartial^XZ"]


def test_job_split_across_many_chunks():
    s = JobSplitter()
    full = b"^XA^FO0,0^FDhello world^FS^XZ"
    out = []
    for byte in full:
        out += s.feed(bytes([byte]))
    assert out == [full]


def test_start_marker_split_across_chunks():
    s = JobSplitter()
    assert s.feed(b"^") == []
    assert s.feed(b"X") == []
    assert s.feed(b"A^FDx^XZ") == [b"^XA^FDx^XZ"]


def test_two_jobs_second_incomplete():
    s = JobSplitter()
    a = b"^XA^FDone^XZ"
    out = s.feed(a + b"^XA^FDtw")
    assert out == [a]
    out2 = s.feed(b"o^XZ")
    assert out2 == [b"^XA^FDtwo^XZ"]


def test_pending_exposed():
    s = JobSplitter()
    s.feed(b"^XA^FDunfinished")
    assert s.pending == b"^XA^FDunfinished"


def test_reset_clears_buffer():
    s = JobSplitter()
    s.feed(b"^XA^FDx")
    s.reset()
    assert s.pending == b""


def test_buffer_overflow_guards():
    s = JobSplitter(max_buffer=16)
    with pytest.raises(BufferError):
        s.feed(b"^XA" + b"D" * 100)


def test_empty_feed():
    s = JobSplitter()
    assert s.feed(b"") == []


def test_noise_only_does_not_grow_buffer():
    s = JobSplitter()
    for _ in range(1000):
        s.feed(b"random noise without markers")
    # bufor nie rośnie w nieskończoność (trzyma tylko możliwy prefiks ^XA)
    assert len(s.pending) < len(b"^XA")

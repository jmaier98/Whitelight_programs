import sys, queue, threading, time, numpy as np
import sounddevice as sd

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QMessageBox

# -------------------------------
#  Speech worker using faster-whisper
# -------------------------------
# --- imports you need at top of file ---
import sys, queue, threading, time, numpy as np
import sounddevice as sd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QMessageBox
from PyQt6.QtGui import QTextCursor

# -------------------------------
#  Low-latency Speech worker (CUDA)
# -------------------------------
class SpeechWorker(QThread):
    new_text = pyqtSignal(str)
    status   = pyqtSignal(str)

    def __init__(self,
                 model_size="base.en",   # faster for English
                 device="cuda",
                 compute_type="float16",
                 samplerate=16000,
                 block_duration=0.2,     # faster blocks
                 chunk_seconds=1.0,      # ~1s latency
                 overlap_seconds=0.2,    # small overlap to catch word boundaries
                 use_vad=False,          # set True after installing onnxruntime
                 parent=None):
        super().__init__(parent)
        self.model_size       = model_size
        self.device           = device
        self.compute_type     = compute_type
        self.samplerate       = samplerate
        self.block_duration   = block_duration
        self.chunk_seconds    = chunk_seconds
        self.overlap_seconds  = overlap_seconds
        self.use_vad          = use_vad

        self._q        = queue.Queue(maxsize=100)
        self._stop_evt = threading.Event()
        self._stream   = None
        self._tail     = np.zeros(0, dtype=np.float32)

        from faster_whisper import WhisperModel
        self.WhisperModel = WhisperModel
        self.model = None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.status.emit(f"Audio status: {status}")
        mono = indata.mean(axis=1).astype(np.float32) if indata.ndim == 2 else indata.astype(np.float32)
        try:
            self._q.put_nowait(mono.copy())
        except queue.Full:
            pass  # drop if UI/thread is briefly behind

    def run(self):
        # Load model on CUDA
        try:
            self.status.emit(f"Loading model '{self.model_size}' on {self.device} ({self.compute_type})…")
            self.model = self.WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        except Exception as e:
            self.status.emit(f"Failed to load model: {e}")
            return

        # Start mic
        try:
            blocksize = int(self.samplerate * self.block_duration)
            self._stream = sd.InputStream(
                samplerate=self.samplerate, channels=1, dtype="float32",
                blocksize=blocksize, callback=self._audio_callback
            )
            self._stream.start()
        except Exception as e:
            self.status.emit(f"Audio error: {e}")
            return

        self.status.emit("Listening…")
        chunk_n = int(self.samplerate * self.chunk_seconds)
        overlap_n = int(self.samplerate * self.overlap_seconds)
        buf = self._tail

        try:
            while not self._stop_evt.is_set():
                # Accumulate until we have a chunk
                try:
                    block = self._q.get(timeout=0.05)
                    buf = np.concatenate((buf, block), dtype=np.float32)
                except queue.Empty:
                    continue

                while buf.size >= chunk_n:
                    # Take a chunk and leave overlap as tail in buffer
                    chunk = buf[:chunk_n]
                    buf   = np.concatenate((buf[chunk_n - overlap_n:],), dtype=np.float32)

                    # Transcribe quickly (greedy, no conditioning)
                    try:
                        segments, info = self.model.transcribe(
                            chunk,
                            language=None,                    # auto
                            beam_size=1,                      # greedy
                            temperature=0.0,
                            condition_on_previous_text=False, # lowers latency
                            vad_filter=self.use_vad,
                            # no_speech_threshold/compression_ratio_threshold left default
                        )

                        text_out = ""
                        for seg in segments:
                            text_out += seg.text.strip() + " "
                        text_out = text_out.strip()
                        if text_out:
                            self.new_text.emit(text_out + "\n")
                    except Exception as te:
                        self.status.emit(f"Transcribe error: {te}")
                        # If it’s a VAD error, advise and continue without VAD next run
        finally:
            if self._stream:
                try:
                    self._stream.stop(); self._stream.close()
                except Exception:
                    pass
            self.status.emit("Audio closed.")

    def stop(self):
        self._stop_evt.set()


# -------------------------------
#  Simple PyQt UI
# -------------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CUDA Whisper — Live STT (Low-Latency POC)")
        self.resize(900, 600)

        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setPlaceholderText("Speak—transcriptions will appear here…")

        self.btn = QPushButton("Start", self)
        self.btn.clicked.connect(self.on_toggle)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text, stretch=1)
        layout.addWidget(self.btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.worker = None
        self._running = False

    def on_toggle(self):
        if not self._running:
            self.worker = SpeechWorker(
                model_size="base.en",      # change to 'small' / 'medium' if you want
                device="cuda",
                compute_type="float16",
                samplerate=16000,
                block_duration=0.2,
                chunk_seconds=1.0,
                overlap_seconds=0.2,
                use_vad=False,            # set True after `pip install onnxruntime-gpu`
            )
            self.worker.new_text.connect(self._append_text)
            self.worker.status.connect(self._append_status)
            self.worker.start()
            self.btn.setText("Stop")
            self._running = True
        else:
            if self.worker:
                self.worker.stop()
                self.worker.wait(3000)
                self.worker = None
            self.btn.setText("Start")
            self._running = False

    def _append_text(self, s: str):
        # fast and auto-scroll
        self.text.append(s)

    def _append_status(self, s: str):
        self.text.append(f"[{time.strftime('%H:%M:%S')}] {s}")

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

# -------------------------------
#  Simple PyQt UI
# -------------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CUDA Whisper — Live STT (POC)")
        self.resize(900, 600)

        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setPlaceholderText("Recognized speech will appear here…")

        self.btn = QPushButton("Start", self)
        self.btn.clicked.connect(self.on_toggle)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text, stretch=1)
        layout.addWidget(self.btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.worker: SpeechWorker | None = None
        self._running = False

    def on_toggle(self):
        if not self._running:
            # Start
            try:
                self.worker = SpeechWorker(
                    model_size="small",   # try 'base' for lower VRAM, 'medium' for quality
                    device="cuda",        # as requested
                    compute_type="float16",
                    samplerate=16000,
                    block_duration=0.5,
                    chunk_seconds=4.0,
                )
                self.worker.new_text.connect(self._append_text)
                self.worker.status.connect(self._append_status)
                self.worker.start()
                self.btn.setText("Stop")
                self._running = True
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
        else:
            # Stop
            if self.worker:
                self.worker.stop()
                self.worker.wait(5000)
                self.worker = None
            self.btn.setText("Start")
            self._running = False

    def _append_text(self, s: str):
        self.text.moveCursor(QTextCursor.MoveOperation.End)
        self.text.insertPlainText(s)
        self.text.moveCursor(QTextCursor.MoveOperation.End)

    def _append_status(self, s: str):
        self.text.moveCursor(QTextCursor.MoveOperation.End)
        self.text.insertPlainText(f"[{time.strftime('%H:%M:%S')}] {s}\n")
        self.text.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event):
        # Ensure worker ends cleanlys
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

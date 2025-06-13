from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioInputTransport,
    LocalAudioTransportParams,
)


class PausableLocalAudioInputTransport(LocalAudioInputTransport):
    """LocalAudioInputTransport with pause/resume capability."""

    def pause_input(self):
        if self._in_stream and self._in_stream.is_active():
            try:
                self._in_stream.stop_stream()
            except Exception:
                pass

    def resume_input(self):
        if self._in_stream and not self._in_stream.is_active():
            try:
                self._in_stream.start_stream()
            except Exception:
                pass


class PausableLocalAudioTransport(LocalAudioTransport):
    """LocalAudioTransport that exposes pause/resume on its input stream."""

    def input(self):  # type: ignore[override]
        if not self._input:
            self._input = PausableLocalAudioInputTransport(self._pyaudio, self._params)
        return self._input

    def pause(self):
        """Pause the audio input stream."""
        try:
            self.input().pause_input()
        except Exception:
            pass

    def resume(self):
        """Resume the audio input stream."""
        try:
            self.input().resume_input()
        except Exception:
            pass

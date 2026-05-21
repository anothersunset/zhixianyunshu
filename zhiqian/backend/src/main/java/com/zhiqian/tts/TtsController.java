package com.zhiqian.tts;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * v2-step-26: TTS 控制器。ProcessBuilder 外调 edge-tts CLI 生 mp3, 返 binary。
 *
 * 未装 edge-tts 时 503 (透明错误), 调方可 fallback browser SpeechSynthesis。
 */
@RestController
@RequestMapping("/api/tts")
public class TtsController {
    private final TtsProperties props;

    public TtsController(TtsProperties props) { this.props = props; }

    @GetMapping("/status")
    public Map<String, Object> status() {
        return Map.of(
            "enabled", props.isEnabled(),
            "engine", props.getEngine(),
            "available", isEdgeTtsAvailable()
        );
    }

    @GetMapping("/speak")
    public ResponseEntity<byte[]> speak(
            @RequestParam String text,
            @RequestParam(required = false) String voice,
            @RequestParam(required = false) String rate,
            @RequestParam(required = false) String volume) {
        if (!props.isEnabled()) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body("tts disabled (set app.tts.enabled=true)".getBytes());
        }
        if (!isEdgeTtsAvailable()) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body("edge-tts CLI not in PATH (pip install edge-tts)".getBytes());
        }
        try {
            byte[] mp3 = renderMp3(
                text,
                voice != null ? voice : props.getVoice(),
                rate != null ? rate : props.getRate(),
                volume != null ? volume : props.getVolume()
            );
            HttpHeaders h = new HttpHeaders();
            h.setContentType(MediaType.parseMediaType("audio/mpeg"));
            h.setCacheControl("no-cache");
            return new ResponseEntity<>(mp3, h, HttpStatus.OK);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(("tts render failed: " + e.getMessage()).getBytes());
        }
    }

    private boolean isEdgeTtsAvailable() {
        try {
            Process p = new ProcessBuilder("edge-tts", "--version")
                    .redirectErrorStream(true).start();
            return p.waitFor(3, TimeUnit.SECONDS) && p.exitValue() == 0;
        } catch (Exception e) {
            return false;
        }
    }

    private byte[] renderMp3(String text, String voice, String rate, String volume)
            throws IOException, InterruptedException {
        Path tmp = Files.createTempFile("zhiqian-tts-", ".mp3");
        try {
            Process p = new ProcessBuilder(
                "edge-tts",
                "--voice", voice,
                "--rate", rate,
                "--volume", volume,
                "--text", text,
                "--write-media", tmp.toString()
            ).redirectErrorStream(true).start();
            if (!p.waitFor(props.getTimeoutSeconds(), TimeUnit.SECONDS)) {
                p.destroyForcibly();
                throw new IOException("edge-tts timeout");
            }
            if (p.exitValue() != 0) {
                throw new IOException("edge-tts exit " + p.exitValue());
            }
            return Files.readAllBytes(tmp);
        } finally {
            Files.deleteIfExists(tmp);
        }
    }
}

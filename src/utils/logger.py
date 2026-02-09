import logging
import sys
from datetime import datetime
from pathlib import Path

def setup_logger(name: str = "SecureAgent", log_file: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

class SecurityEventLogger:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.events = []
    
    def log_injection_attempt(self, input_text: str, pattern: str, severity: str = "HIGH"):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "INJECTION_ATTEMPT",
            "pattern": pattern,
            "severity": severity,
            "input_preview": input_text[:100]
        }
        self.events.append(event)
        self.logger.warning(f"[SECURITY] Injection attempt detected: {pattern} (Severity: {severity})")
    
    def log_toxicity_block(self, output_text: str, score: float):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "TOXICITY_BLOCK",
            "score": score,
            "output_preview": output_text[:100]
        }
        self.events.append(event)
        self.logger.warning(f"[SECURITY] Toxic output blocked: score={score:.3f}")
    
    def log_constitutional_violation(self, principle: str, score: float):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "CONSTITUTIONAL_VIOLATION",
            "principle": principle,
            "score": score
        }
        self.events.append(event)
        self.logger.warning(f"[SECURITY] Constitutional violation: {principle} (score={score:.3f})")
    
    def log_sanitization(self, original: str, cleaned: str):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "INPUT_SANITIZED",
            "changes": len(original) - len(cleaned)
        }
        self.events.append(event)
        self.logger.info(f"[SECURITY] Input sanitized: {len(original)} -> {len(cleaned)} chars")
    
    def get_event_summary(self):
        return {
            "total_events": len(self.events),
            "by_type": {
                event_type: len([e for e in self.events if e["event_type"] == event_type])
                for event_type in set(e["event_type"] for e in self.events)
            }
        }
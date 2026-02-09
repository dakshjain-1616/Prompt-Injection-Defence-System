import re
import unicodedata
from typing import Dict, List, Tuple
from collections import Counter
import math
import yaml
from pathlib import Path

class SecurityViolation(Exception):
    def __init__(self, message: str, violation_type: str, details: Dict = None):
        super().__init__(message)
        self.violation_type = violation_type
        self.details = details or {}

class InputSanitizer:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "security_policies.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.injection_patterns = self._compile_patterns()
        self.blacklist = set(self.config.get('blacklist_keywords', []))
        self.constraints = self.config.get('input_constraints', {})
    
    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        compiled = {}
        for category, patterns in self.config.get('injection_patterns', {}).items():
            compiled[category] = [re.compile(p) for p in patterns]
        return compiled
    
    def normalize_encoding(self, text: str) -> str:
        text = unicodedata.normalize('NFKC', text)
        
        text = text.encode('ascii', 'ignore').decode('ascii')
        
        homoglyphs = {
            'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
            'ı': 'i', 'ο': 'o', 'ѕ': 's', 'һ': 'h', 'ј': 'j', 'ӏ': 'l'
        }
        for homoglyph, replacement in homoglyphs.items():
            text = text.replace(homoglyph, replacement)
        
        return text
    
    def calculate_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        char_counts = Counter(text)
        length = len(text)
        entropy = -sum((count/length) * math.log2(count/length) for count in char_counts.values())
        return entropy
    
    def calculate_repetition_ratio(self, text: str) -> float:
        if len(text) < 10:
            return 0.0
        words = text.lower().split()
        if not words:
            return 0.0
        word_counts = Counter(words)
        max_repetitions = max(word_counts.values())
        return max_repetitions / len(words)
    
    def detect_injection_patterns(self, text: str) -> List[Tuple[str, str]]:
        detections = []
        normalized_text = self.normalize_encoding(text)
        
        for category, patterns in self.injection_patterns.items():
            for pattern in patterns:
                if pattern.search(normalized_text):
                    match = pattern.search(normalized_text).group()
                    detections.append((category, match))
        
        return detections
    
    def detect_blacklist_keywords(self, text: str) -> List[str]:
        normalized_text = self.normalize_encoding(text.lower())
        found = []
        for keyword in self.blacklist:
            if keyword.lower() in normalized_text:
                found.append(keyword)
        return found
    
    def check_constraints(self, text: str) -> List[str]:
        violations = []
        
        max_length = self.constraints.get('max_length', 10000)
        if len(text) > max_length:
            violations.append(f"Input exceeds max length: {len(text)} > {max_length}")
        
        max_rep_ratio = self.constraints.get('max_repetition_ratio', 0.3)
        rep_ratio = self.calculate_repetition_ratio(text)
        if rep_ratio > max_rep_ratio:
            violations.append(f"Excessive repetition: {rep_ratio:.2f} > {max_rep_ratio}")
        
        min_entropy = self.constraints.get('min_entropy', 2.0)
        entropy = self.calculate_entropy(text)
        if len(text) > 50 and entropy < min_entropy:
            violations.append(f"Suspiciously low entropy: {entropy:.2f} < {min_entropy}")
        
        return violations
    
    def sanitize(self, text: str, strict: bool = False) -> Tuple[str, Dict]:
        report = {
            "original_length": len(text),
            "normalized": False,
            "injections_detected": [],
            "blacklist_matches": [],
            "constraint_violations": [],
            "security_risk": "NONE"
        }
        
        normalized_text = self.normalize_encoding(text)
        if normalized_text != text:
            report["normalized"] = True
        
        injections = self.detect_injection_patterns(normalized_text)
        if injections:
            report["injections_detected"] = [{"category": cat, "match": match} for cat, match in injections]
            report["security_risk"] = "HIGH"
            if strict:
                raise SecurityViolation(
                    f"Prompt injection detected: {injections[0][0]}",
                    violation_type="INJECTION_PATTERN",
                    details=report
                )
        
        blacklist_matches = self.detect_blacklist_keywords(normalized_text)
        if blacklist_matches:
            report["blacklist_matches"] = blacklist_matches
            report["security_risk"] = "HIGH" if not report["security_risk"] == "HIGH" else "HIGH"
            if strict:
                raise SecurityViolation(
                    f"Blacklisted keywords detected: {blacklist_matches}",
                    violation_type="BLACKLIST",
                    details=report
                )
        
        constraint_violations = self.check_constraints(normalized_text)
        if constraint_violations:
            report["constraint_violations"] = constraint_violations
            report["security_risk"] = "MEDIUM"
        
        cleaned_text = normalized_text
        for keyword in blacklist_matches:
            cleaned_text = re.sub(re.escape(keyword), "[FILTERED]", cleaned_text, flags=re.IGNORECASE)
        
        report["cleaned_length"] = len(cleaned_text)
        
        return cleaned_text, report
    
    def is_safe(self, text: str) -> bool:
        try:
            _, report = self.sanitize(text, strict=False)
            return report["security_risk"] in ["NONE", "LOW"]
        except SecurityViolation:
            return False
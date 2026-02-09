import re
from typing import Dict, Tuple
import yaml
from pathlib import Path

class OutputValidator:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "security_policies.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.output_config = self.config.get('output_validation', {})
        self.toxicity_threshold = self.output_config.get('toxicity_threshold', 0.7)
        self.max_output_length = self.output_config.get('max_output_length', 5000)
        
        self.toxicity_model = None
        self.tokenizer = None
        self._load_toxicity_model()
    
    def _load_toxicity_model(self):
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            
            model_name = "unitary/toxic-bert"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.eval()
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
        except Exception as e:
            self.model = None
            self.tokenizer = None
    
    def check_toxicity(self, text: str) -> Tuple[float, Dict]:
        if self.model is None or self.tokenizer is None:
            return self._rule_based_toxicity(text)
        
        try:
            import torch
            
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1)
                toxic_label_idx = 0
                toxicity_score = probs[0][toxic_label_idx].item()
            
            return toxicity_score, {"method": "model", "model": "unitary/toxic-bert"}
        except Exception as e:
            return self._rule_based_toxicity(text)
    
    def _rule_based_toxicity(self, text: str) -> Tuple[float, Dict]:
        toxic_patterns = [
            r'\b(hate|stupid|idiot|dumb|kill|attack|hurt|destroy|harm)\b',
            r'\b(offensive|violent|harmful|dangerous|illegal)\b'
        ]
        
        text_lower = text.lower()
        matches = sum(1 for pattern in toxic_patterns if re.search(pattern, text_lower))
        score = min(matches * 0.4, 0.95)
        
        return score, {"method": "rule_based", "matches": matches}
    
    def check_format_compliance(self, text: str) -> Dict:
        issues = []
        
        if len(text) > self.max_output_length:
            issues.append(f"Output too long: {len(text)} > {self.max_output_length}")
        
        if not text.strip():
            issues.append("Output is empty or whitespace only")
        
        suspicious_patterns = [
            (r'<script', "Contains script tag"),
            (r'javascript:', "Contains javascript protocol"),
            (r'on\w+\s*=', "Contains event handler attribute"),
            (r'\[SYSTEM\]', "Contains system marker"),
            (r'\[ADMIN\]', "Contains admin marker")
        ]
        
        for pattern, description in suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(description)
        
        return {
            "compliant": len(issues) == 0,
            "issues": issues
        }
    
    def validate(self, text: str) -> Tuple[bool, Dict]:
        report = {
            "passed": True,
            "toxicity": {},
            "format": {},
            "violations": []
        }
        
        toxicity_score, tox_details = self.check_toxicity(text)
        report["toxicity"] = {
            "score": toxicity_score,
            "threshold": self.toxicity_threshold,
            "details": tox_details
        }
        
        if toxicity_score > self.toxicity_threshold:
            report["passed"] = False
            report["violations"].append(f"Toxicity score {toxicity_score:.3f} exceeds threshold {self.toxicity_threshold}")
        
        format_check = self.check_format_compliance(text)
        report["format"] = format_check
        
        if not format_check["compliant"]:
            report["passed"] = False
            report["violations"].extend(format_check["issues"])
        
        return report["passed"], report
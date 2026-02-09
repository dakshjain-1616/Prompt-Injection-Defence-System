import re
from typing import Dict, List, Tuple
import yaml
from pathlib import Path

class ConstitutionalJudge:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "security_policies.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.principles = self.config.get('constitutional_principles', {})
    
    def evaluate_safety(self, text: str, context: Dict = None) -> Tuple[float, List[str]]:
        principle = self.principles.get('safety', {})
        violations = []
        
        violation_keywords = principle.get('violation_keywords', [])
        text_lower = text.lower()
        
        for keyword in violation_keywords:
            if keyword.lower() in text_lower:
                violations.append(f"Safety violation: contains '{keyword}'")
        
        harmful_patterns = [
            (r'\b(how to|here\'?s how|instructions? (to|for)) (make|build|create|construct).{0,20}(bomb|weapon|poison|explosive)\b', "Instructions for harmful items"),
            (r'\b(kill|murder|hurt|harm|attack).{0,20}(someone|people|person|them|him|her)\b', "Violence against people"),
            (r'\b(illegal|criminal) (activity|act|action)\b', "Illegal activity"),
            (r'\bviolent(ly)?\b', "Violent content"),
            (r'\b(make up|fabricate).{0,30}(weapon|bomb|dangerous|harmful)\b', "Fabrication about dangerous items")
        ]
        
        for pattern, description in harmful_patterns:
            if re.search(pattern, text_lower):
                violations.append(f"Safety violation: {description}")
        
        score = 1.0 - (len(violations) * 0.35)
        score = max(0.0, min(1.0, score))
        
        return score, violations
    
    def evaluate_honesty(self, text: str, context: Dict = None) -> Tuple[float, List[str]]:
        principle = self.principles.get('honesty', {})
        violations = []
        
        violation_patterns = principle.get('violation_patterns', [])
        text_lower = text.lower()
        
        for pattern in violation_patterns:
            if pattern.lower() in text_lower:
                violations.append(f"Honesty concern: contains '{pattern}'")
        
        deceptive_indicators = [
            (r'\b(definitely|certainly|absolutely) (true|correct|accurate)\b', "Overconfidence without evidence"),
            (r'\b(i (am sure|guarantee|promise)|absolutely guarantee)\b', "Inappropriate certainty"),
            (r'\b(everyone knows|everybody agrees|it is obvious)\b', "False consensus")
        ]
        
        for pattern, description in deceptive_indicators:
            if re.search(pattern, text_lower):
                violations.append(f"Honesty concern: {description}")
        
        score = 1.0 - (len(violations) * 0.25)
        score = max(0.0, min(1.0, score))
        
        return score, violations
    
    def evaluate_helpfulness(self, text: str, context: Dict = None) -> Tuple[float, List[str]]:
        principle = self.principles.get('helpfulness', {})
        issues = []
        
        if len(text.strip()) < 10:
            issues.append("Response too short to be helpful")
        
        if context and 'user_query' in context:
            query_lower = context['user_query'].lower()
            text_lower = text.lower()
            
            query_words = set(query_lower.split())
            text_words = set(text_lower.split())
            overlap = len(query_words.intersection(text_words))
            
            if overlap < 2 and len(query_words) > 5:
                issues.append("Response may not be relevant to user query")
        
        unhelpful_patterns = [
            (r'\bi (cannot|can\'t|won\'t) help\b', "Outright refusal without explanation"),
            (r'\bi don\'t know\b.*$', "Non-informative response"),
            (r'^(sorry|apologies)\.?\s*$', "Apology without substance")
        ]
        
        for pattern, description in unhelpful_patterns:
            if re.search(pattern, text.lower()):
                issues.append(f"Helpfulness concern: {description}")
        
        score = 1.0 - (len(issues) * 0.25)
        score = max(0.0, min(1.0, score))
        
        return score, issues
    
    def evaluate(self, text: str, context: Dict = None) -> Dict:
        results = {
            "overall_score": 0.0,
            "passed": True,
            "principle_scores": {},
            "violations": []
        }
        
        safety_score, safety_violations = self.evaluate_safety(text, context)
        results["principle_scores"]["safety"] = {
            "score": safety_score,
            "weight": self.principles.get('safety', {}).get('weight', 1.0),
            "violations": safety_violations
        }
        
        honesty_score, honesty_violations = self.evaluate_honesty(text, context)
        results["principle_scores"]["honesty"] = {
            "score": honesty_score,
            "weight": self.principles.get('honesty', {}).get('weight', 0.9),
            "violations": honesty_violations
        }
        
        helpfulness_score, helpfulness_issues = self.evaluate_helpfulness(text, context)
        results["principle_scores"]["helpfulness"] = {
            "score": helpfulness_score,
            "weight": self.principles.get('helpfulness', {}).get('weight', 0.8),
            "violations": helpfulness_issues
        }
        
        total_weight = sum(p["weight"] for p in results["principle_scores"].values())
        weighted_sum = sum(p["score"] * p["weight"] for p in results["principle_scores"].values())
        results["overall_score"] = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        threshold = 0.65
        if results["overall_score"] < threshold:
            results["passed"] = False
        
        for principle_name, principle_data in results["principle_scores"].items():
            if principle_data["violations"]:
                results["violations"].extend(principle_data["violations"])
        
        return results
    
    def suggest_refinement(self, text: str, evaluation: Dict) -> str:
        if evaluation["passed"]:
            return text
        
        suggestions = []
        for principle_name, principle_data in evaluation["principle_scores"].items():
            if principle_data["violations"]:
                suggestions.append(f"Address {principle_name} concerns: {principle_data['violations'][0]}")
        
        refinement_prompt = f"Original response has constitutional violations. {' '.join(suggestions[:2])}"
        
        return refinement_prompt
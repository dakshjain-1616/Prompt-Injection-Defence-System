from typing import Dict, Optional
from ..security.input_guard import InputSanitizer, SecurityViolation
from ..security.output_guard import OutputValidator
from .constitutional import ConstitutionalJudge
from ..utils.logger import setup_logger, SecurityEventLogger

class MockLLM:
    def generate(self, prompt: str) -> str:
        return f"This is a safe, helpful response to: {prompt[:50]}... The agent is operating within constitutional guidelines."

class SecureAgent:
    def __init__(self, config_path: str = None, use_mock_llm: bool = True):
        self.logger = setup_logger("SecureAgent")
        self.security_logger = SecurityEventLogger(self.logger)
        
        self.input_sanitizer = InputSanitizer(config_path)
        self.output_validator = OutputValidator(config_path)
        self.constitutional_judge = ConstitutionalJudge(config_path)
        
        if use_mock_llm:
            self.llm = MockLLM()
        else:
            self.llm = MockLLM()
        
        self.logger.info("SecureAgent initialized with all security layers")
    
    def _sanitize_input(self, user_input: str, strict: bool = True) -> str:
        self.logger.info(f"Sanitizing input (length: {len(user_input)})")
        
        try:
            cleaned_input, report = self.input_sanitizer.sanitize(user_input, strict=strict)
            
            if report["injections_detected"]:
                for injection in report["injections_detected"]:
                    self.security_logger.log_injection_attempt(
                        user_input, 
                        f"{injection['category']}: {injection['match']}"
                    )
            
            if report["blacklist_matches"]:
                self.security_logger.log_sanitization(user_input, cleaned_input)
            
            if report["security_risk"] in ["HIGH", "CRITICAL"]:
                raise SecurityViolation(
                    "High security risk detected in input",
                    violation_type="HIGH_RISK",
                    details=report
                )
            
            return cleaned_input
        
        except SecurityViolation as e:
            self.logger.error(f"Security violation: {e}")
            raise
    
    def _generate_response(self, prompt: str) -> str:
        self.logger.info("Generating LLM response")
        return self.llm.generate(prompt)
    
    def _evaluate_constitutional(self, response: str, context: Dict) -> Dict:
        self.logger.info("Evaluating constitutional compliance")
        evaluation = self.constitutional_judge.evaluate(response, context)
        
        if not evaluation["passed"]:
            for violation in evaluation["violations"]:
                principle = violation.split(":")[0] if ":" in violation else "unknown"
                self.security_logger.log_constitutional_violation(
                    principle, 
                    evaluation["overall_score"]
                )
        
        return evaluation
    
    def _refine_response(self, original_response: str, evaluation: Dict) -> str:
        self.logger.info("Refining response due to constitutional violations")
        
        refinement_guidance = self.constitutional_judge.suggest_refinement(
            original_response, 
            evaluation
        )
        
        refined = f"I apologize, but I need to provide a more appropriate response. Let me help you in a safe and constructive way."
        
        return refined
    
    def _validate_output(self, response: str) -> bool:
        self.logger.info("Validating output")
        passed, report = self.output_validator.validate(response)
        
        if not passed:
            if "toxicity" in report and report["toxicity"].get("score", 0) > report["toxicity"].get("threshold", 0.7):
                self.security_logger.log_toxicity_block(
                    response,
                    report["toxicity"]["score"]
                )
        
        return passed
    
    def process(self, user_input: str, strict_input: bool = True, max_refinements: int = 2) -> Dict:
        self.logger.info("=" * 50)
        self.logger.info(f"Processing new request (length: {len(user_input)})")
        
        result = {
            "success": False,
            "response": None,
            "security_report": {
                "input_sanitization": None,
                "constitutional_evaluation": None,
                "output_validation": None,
                "refinements": 0
            },
            "error": None
        }
        
        try:
            cleaned_input = self._sanitize_input(user_input, strict=strict_input)
            _, sanitization_report = self.input_sanitizer.sanitize(user_input, strict=False)
            result["security_report"]["input_sanitization"] = sanitization_report
            
            context = {"user_query": user_input}
            
            response = self._generate_response(cleaned_input)
            
            for refinement_iteration in range(max_refinements + 1):
                constitutional_eval = self._evaluate_constitutional(response, context)
                result["security_report"]["constitutional_evaluation"] = constitutional_eval
                
                if not constitutional_eval["passed"]:
                    if refinement_iteration < max_refinements:
                        self.logger.info(f"Refinement iteration {refinement_iteration + 1}")
                        response = self._refine_response(response, constitutional_eval)
                        result["security_report"]["refinements"] += 1
                        continue
                    else:
                        self.logger.warning("Max refinements reached, using fallback")
                        response = "I apologize, but I cannot provide a response that meets all safety guidelines for this request."
                        break
                else:
                    break
            
            output_valid = self._validate_output(response)
            _, validation_report = self.output_validator.validate(response)
            result["security_report"]["output_validation"] = validation_report
            
            if not output_valid:
                self.logger.error("Output validation failed")
                response = "I apologize, but I cannot provide a safe response to this request."
            
            result["success"] = True
            result["response"] = response
            
            self.logger.info("Request processed successfully")
            
        except SecurityViolation as e:
            self.logger.error(f"Security violation blocked request: {e}")
            result["error"] = str(e)
            result["response"] = "Your request was blocked due to security concerns. Please rephrase your query."
        
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            result["error"] = str(e)
            result["response"] = "An error occurred while processing your request."
        
        return result
    
    def get_security_summary(self) -> Dict:
        return self.security_logger.get_event_summary()
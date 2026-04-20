#!/usr/bin/env python
"""
Evaluation script for Prompt Injection Defense System.
Runs the evaluation dataset through the detector and outputs metrics to scorecard.json.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from security.input_guard import InputSanitizer


def load_dataset(dataset_path: str) -> dict:
    """Load the evaluation dataset from JSON file."""
    with open(dataset_path, 'r') as f:
        return json.load(f)


def evaluate_entry(sanitizer: InputSanitizer, entry: dict) -> dict:
    """
    Evaluate a single entry through the InputSanitizer.
    Returns evaluation results with detection status.
    """
    text = entry["text"]
    expected_label = entry["label"]
    category = entry["category"]
    
    # Run through sanitizer
    cleaned_text, report = sanitizer.sanitize(text, strict=False)
    
    # Determine if blocked
    is_blocked = report["security_risk"] == "HIGH"
    
    # Determine if detection was correct
    if expected_label == "attack":
        correctly_detected = is_blocked  # True positive
        false_negative = not is_blocked  # Missed attack
        false_positive = False
        true_negative = False
    else:  # benign
        correctly_detected = not is_blocked  # True negative
        false_positive = is_blocked  # Blocked benign
        false_negative = False
        true_negative = not is_blocked
    
    return {
        "id": entry["id"],
        "category": category,
        "expected_label": expected_label,
        "is_blocked": is_blocked,
        "correctly_detected": correctly_detected,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "security_risk": report["security_risk"],
        "injections_detected": report.get("injections_detected", []),
        "blacklist_matches": report.get("blacklist_matches", [])
    }


def calculate_metrics(results: list) -> dict:
    """Calculate overall metrics from evaluation results."""
    total = len(results)
    
    # Count by category
    category_stats = defaultdict(lambda: {
        "total": 0,
        "correct": 0,
        "false_positives": 0,
        "false_negatives": 0
    })
    
    # Overall counters
    true_positives = 0
    true_negatives = 0
    false_positives = 0
    false_negatives = 0
    
    for result in results:
        cat = result["category"]
        category_stats[cat]["total"] += 1
        
        if result["correctly_detected"]:
            category_stats[cat]["correct"] += 1
        
        if result["false_positive"]:
            category_stats[cat]["false_positives"] += 1
            false_positives += 1
        
        if result["false_negative"]:
            category_stats[cat]["false_negatives"] += 1
            false_negatives += 1
        
        # Count TP/TN
        if result["expected_label"] == "attack" and result["is_blocked"]:
            true_positives += 1
        elif result["expected_label"] == "benign" and not result["is_blocked"]:
            true_negatives += 1
    
    # Calculate per-category accuracy
    category_metrics = {}
    for cat, stats in category_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        category_metrics[cat] = {
            "total_samples": stats["total"],
            "correct_detections": stats["correct"],
            "accuracy": round(accuracy, 4),
            "false_positives": stats["false_positives"],
            "false_negatives": stats["false_negatives"]
        }
    
    # Calculate overall metrics
    total_attacks = sum(1 for r in results if r["expected_label"] == "attack")
    total_benign = sum(1 for r in results if r["expected_label"] == "benign")
    
    # Accuracy
    accuracy = (true_positives + true_negatives) / total if total > 0 else 0
    
    # Precision: TP / (TP + FP)
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    
    # Recall: TP / (TP + FN)
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    
    # F1 Score
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # False Positive Rate: FP / (FP + TN)
    fpr = false_positives / (false_positives + true_negatives) if (false_positives + true_negatives) > 0 else 0
    
    # False Negative Rate: FN / (FN + TP)
    fnr = false_negatives / (false_negatives + true_positives) if (false_negatives + true_positives) > 0 else 0
    
    return {
        "overall": {
            "total_samples": total,
            "total_attacks": total_attacks,
            "total_benign": total_benign,
            "true_positives": true_positives,
            "true_negatives": true_negatives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "false_positive_rate": round(fpr, 4),
            "false_negative_rate": round(fnr, 4)
        },
        "by_category": category_metrics
    }


def generate_scorecard(metrics: dict, results: list) -> dict:
    """Generate the final scorecard JSON structure."""
    return {
        "metadata": {
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "evaluator": "Prompt Injection Defense System Evaluation Script",
            "dataset": "evaluation_dataset.json"
        },
        "summary": {
            "status": "PASS" if metrics["overall"]["accuracy"] >= 0.8 else "NEEDS_IMPROVEMENT",
            "total_evaluated": metrics["overall"]["total_samples"],
            "attacks_detected": metrics["overall"]["true_positives"],
            "attacks_missed": metrics["overall"]["false_negatives"],
            "benign_blocked": metrics["overall"]["false_positives"],
            "benign_allowed": metrics["overall"]["true_negatives"]
        },
        "metrics": metrics,
        "detailed_results": results
    }


def print_scorecard(scorecard: dict):
    """Print a formatted scorecard to console."""
    print("\n" + "=" * 70)
    print("PROMPT INJECTION DEFENSE SYSTEM - EVALUATION SCORECARD")
    print("=" * 70)
    
    summary = scorecard["summary"]
    print(f"\n📊 OVERALL STATUS: {summary['status']}")
    print(f"   Total Evaluated: {summary['total_evaluated']}")
    print(f"   Attacks Detected: {summary['attacks_detected']}")
    print(f"   Attacks Missed: {summary['attacks_missed']}")
    print(f"   Benign Blocked (False Positives): {summary['benign_blocked']}")
    print(f"   Benign Allowed (True Negatives): {summary['benign_allowed']}")
    
    overall = scorecard["metrics"]["overall"]
    print("\n📈 OVERALL METRICS:")
    print(f"   Accuracy:  {overall['accuracy']:.2%}")
    print(f"   Precision: {overall['precision']:.2%}")
    print(f"   Recall:    {overall['recall']:.2%}")
    print(f"   F1 Score:  {overall['f1_score']:.4f}")
    print(f"   FPR:       {overall['false_positive_rate']:.2%}")
    print(f"   FNR:       {overall['false_negative_rate']:.2%}")
    
    print("\n📋 PER-CATEGORY PERFORMANCE:")
    for category, cat_metrics in scorecard["metrics"]["by_category"].items():
        print(f"   {category:20s}: Accuracy {cat_metrics['accuracy']:.2%} "
              f"(FP: {cat_metrics['false_positives']}, FN: {cat_metrics['false_negatives']})")
    
    print("\n" + "=" * 70)
    print("Scorecard saved to: data/scorecard.json")
    print("=" * 70 + "\n")


def main():
    """Main evaluation function."""
    print("🚀 Starting Prompt Injection Defense System Evaluation...")
    
    # Paths
    dataset_path = project_root / "data" / "evaluation_dataset.json"
    scorecard_path = project_root / "data" / "scorecard.json"
    
    # Check if dataset exists
    if not dataset_path.exists():
        print(f"❌ Error: Dataset not found at {dataset_path}")
        sys.exit(1)
    
    print(f"📁 Loading dataset from: {dataset_path}")
    dataset = load_dataset(str(dataset_path))
    
    # Initialize sanitizer
    print("🔧 Initializing InputSanitizer...")
    sanitizer = InputSanitizer()
    
    # Evaluate all entries
    print(f"🧪 Evaluating {len(dataset['entries'])} entries...")
    results = []
    
    for i, entry in enumerate(dataset["entries"], 1):
        result = evaluate_entry(sanitizer, entry)
        results.append(result)
        
        # Progress indicator
        if i % 20 == 0 or i == len(dataset["entries"]):
            print(f"   Progress: {i}/{len(dataset['entries'])} entries evaluated")
    
    # Calculate metrics
    print("📊 Calculating metrics...")
    metrics = calculate_metrics(results)
    
    # Generate scorecard
    scorecard = generate_scorecard(metrics, results)
    
    # Save scorecard
    print(f"💾 Saving scorecard to: {scorecard_path}")
    with open(scorecard_path, 'w') as f:
        json.dump(scorecard, f, indent=2)
    
    # Print formatted scorecard
    print_scorecard(scorecard)
    
    # Return exit code based on performance
    if metrics["overall"]["accuracy"] >= 0.8:
        print("✅ Evaluation PASSED - Accuracy >= 80%")
        return 0
    else:
        print("⚠️  Evaluation NEEDS IMPROVEMENT - Accuracy < 80%")
        return 1


if __name__ == "__main__":
    sys.exit(main())

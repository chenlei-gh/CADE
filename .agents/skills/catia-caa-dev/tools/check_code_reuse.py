#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Code Reuse Checker for CATIA CAA Development
Prevents "reinventing the wheel" by analyzing existing codebase
Integrated with evolution system for continuous improvement
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration
# Derive workspace from script location (go up 4 levels from tools/)
WORKSPACE = str(Path(__file__).parent.parent.parent.parent.parent)
CAA_SYSTEM_PATH = os.path.join(WORKSPACE, "CAASystem.edu")

# Anti-pattern keywords
ANTI_PATTERNS = {
    "collections": {
        "keywords": ["List", "Array", "Vector", "Map", "Queue", "Stack", "Set"],
        "suggestion": "Use CATListOf<T> instead of custom collections",
        "library": "System (CATListOf*)",
    },
    "math": {
        "keywords": [
            "Math",
            "Point",
            "Vector",
            "Matrix",
            "Transform",
            "Distance",
            "Angle",
        ],
        "suggestion": "Use CATMath* classes instead of custom math",
        "library": "Mathematics (CATMath*)",
    },
    "strings": {
        "keywords": ["String", "Text", "Char"],
        "suggestion": "Use CATUnicodeString instead of custom string handling",
        "library": "System (CATUnicodeString)",
    },
    "geometry": {
        "keywords": ["Geometry", "Surface", "Curve", "Line", "Circle", "Shape"],
        "suggestion": "Use CAA geometric objects instead of custom geometry",
        "library": "GeometricObjects",
    },
    "ui": {
        "keywords": ["Dialog", "Button", "Window", "Panel", "Widget"],
        "suggestion": "Use CAA dialog framework instead of custom UI",
        "library": "CATDialogEngine",
    },
}

# CAA library recommendations
CAA_LIBRARIES = {
    "System": "Always required - base framework",
    "JS0GROUP": "Core services and infrastructure",
    "Mathematics": "Math operations, vectors, matrices",
    "GeometricObjects": "Geometric shapes and operations",
    "CATDialogEngine": "User interface dialogs",
    "ObjectModelerBase": "Object modeling framework",
    "VisualizationBase": "3D visualization",
    "KnowledgeInterfaces": "Parameters and formulas",
}


class CodeReuseChecker:
    def __init__(self, component_name: str, interface_name: str = None):
        self.component_name = component_name
        self.interface_name = interface_name
        self.results = {
            "component_name": component_name,
            "interface_name": interface_name,
            "duplicate_components": [],
            "duplicate_interfaces": [],
            "similar_in_samples": [],
            "anti_patterns": [],
            "suggested_libraries": ["System", "JS0GROUP"],
            "recommendation": "PROCEED",
            "warnings": [],
        }

    def check_duplicate_components(self) -> List[str]:
        """Search for existing components with same/similar name"""
        print(f"[1/6] Searching for duplicate components...")

        duplicates = []
        for edu_dir in Path(WORKSPACE).glob("*.edu"):
            for cpp_file in edu_dir.rglob(f"*{self.component_name}*.cpp"):
                duplicates.append(str(cpp_file))
                print(f"  FOUND: {cpp_file}")

        self.results["duplicate_components"] = duplicates

        if duplicates:
            self.results["warnings"].append(
                f"Found {len(duplicates)} similar component(s). Consider reusing existing code."
            )
            self.results["recommendation"] = "REVIEW_REQUIRED"
        else:
            print("  [v] No duplicate components found")

        return duplicates

    def check_duplicate_interfaces(self) -> List[str]:
        """Search for existing interfaces with same/similar name"""
        if not self.interface_name:
            print("[2/6] Skipping interface check (no interface name provided)")
            return []

        print(f"[2/6] Searching for duplicate interfaces...")

        duplicates = []
        for edu_dir in Path(WORKSPACE).glob("*.edu"):
            pub_interfaces = edu_dir / "PublicInterfaces"
            if pub_interfaces.exists():
                for h_file in pub_interfaces.glob(f"{self.interface_name}.h"):
                    duplicates.append(str(h_file))
                    print(f"  FOUND: {h_file}")

        self.results["duplicate_interfaces"] = duplicates

        if duplicates:
            self.results["warnings"].append(
                f"Found {len(duplicates)} similar interface(s). Interface may already exist!"
            )
            self.results["recommendation"] = "REVIEW_REQUIRED"
        else:
            print("  [v] No duplicate interfaces found")

        return duplicates

    def check_caa_samples(self) -> List[str]:
        """Check CAASystem.edu for similar examples"""
        print(f"[3/6] Checking CAASystem.edu samples...")

        if not Path(CAA_SYSTEM_PATH).exists():
            print("  ⚠ CAASystem.edu not found")
            return []

        similar = []
        for file in Path(CAA_SYSTEM_PATH).rglob("*"):
            if file.is_file() and self.component_name.lower() in file.name.lower():
                if file.suffix in [".h", ".cpp"]:
                    similar.append(str(file))
                    print(f"  INFO: {file}")

        self.results["similar_in_samples"] = similar

        if similar:
            print(f"  ℹ Found {len(similar)} example(s) in CAASystem.edu")
        else:
            print("  [v] No examples in CAASystem.edu")

        return similar

    def check_anti_patterns(self) -> List[Dict]:
        """Detect anti-patterns in component name"""
        print(f"[4/6] Checking for anti-patterns...")

        detected = []
        for pattern_name, pattern_data in ANTI_PATTERNS.items():
            for keyword in pattern_data["keywords"]:
                if keyword.lower() in self.component_name.lower():
                    detected.append(
                        {
                            "pattern": pattern_name,
                            "keyword": keyword,
                            "suggestion": pattern_data["suggestion"],
                            "library": pattern_data["library"],
                        }
                    )
                    print(f"  ⚠ {pattern_name.upper()}: {pattern_data['suggestion']}")

                    # Add suggested library
                    lib_name = pattern_data["library"].split()[0]
                    if lib_name not in self.results["suggested_libraries"]:
                        self.results["suggested_libraries"].append(lib_name)

                    break  # Only report once per pattern type

        self.results["anti_patterns"] = detected

        if detected:
            self.results["warnings"].append(
                f"Detected {len(detected)} potential anti-pattern(s). Consider using CAA libraries."
            )
            if self.results["recommendation"] == "PROCEED":
                self.results["recommendation"] = "USE_CAA_LIBRARIES"
        else:
            print("  [v] No anti-patterns detected")

        return detected

    def analyze_functionality(self) -> Dict[str, str]:
        """Analyze what functionality is needed and suggest libraries"""
        print(f"[5/6] Analyzing functionality...")

        suggestions = {}
        component_lower = self.component_name.lower()

        # Analyze by keywords
        if any(kw in component_lower for kw in ["file", "document", "save", "load"]):
            suggestions["JS0FM"] = "File management operations"
            self.results["suggested_libraries"].append("JS0FM")

        if any(kw in component_lower for kw in ["param", "formula", "knowledge"]):
            suggestions["KnowledgeInterfaces"] = "Parameters and formulas"
            self.results["suggested_libraries"].append("KnowledgeInterfaces")

        if any(kw in component_lower for kw in ["visual", "render", "display", "3d"]):
            suggestions["VisualizationBase"] = "3D visualization"
            self.results["suggested_libraries"].append("VisualizationBase")

        # Remove duplicates
        self.results["suggested_libraries"] = list(
            set(self.results["suggested_libraries"])
        )

        if suggestions:
            for lib, reason in suggestions.items():
                print(f"  → {lib}: {reason}")
        else:
            print("  [v] Using base libraries only")

        return suggestions

    def generate_report(self) -> Dict:
        """Generate final report"""
        print(f"[6/6] Generating report...")

        # Calculate severity
        severity = "OK"
        if self.results["duplicate_components"]:
            severity = "CRITICAL"
        elif self.results["duplicate_interfaces"]:
            severity = "CRITICAL"
        elif self.results["anti_patterns"]:
            severity = "WARNING"

        self.results["severity"] = severity

        print("\n" + "=" * 50)
        print("REPORT SUMMARY")
        print("=" * 50)
        print(f"Component: {self.component_name}")
        if self.interface_name:
            print(f"Interface: {self.interface_name}")
        print(f"Severity: {severity}")
        print(f"Recommendation: {self.results['recommendation']}")
        print()

        if self.results["warnings"]:
            print("Warnings:")
            for warning in self.results["warnings"]:
                print(f"  ! {warning}")
            print()

        print("Suggested CAA Libraries:")
        for lib in self.results["suggested_libraries"]:
            if lib in CAA_LIBRARIES:
                print(f"  - {lib}: {CAA_LIBRARIES[lib]}")
            else:
                print(f"  - {lib}")
        print()

        # Final recommendation
        if severity == "CRITICAL":
            print("[FAIL] STOP: Duplicate component/interface found!")
            print("   Action: Review existing code before creating new component")
        elif severity == "WARNING":
            print("⚠ CAUTION: Potential anti-pattern detected")
            print("   Action: Verify you cannot use CAA libraries instead")
        else:
            print("[v] OK: No major issues detected")
            print("   Action: Proceed with component creation")

        print("=" * 50)

        return self.results

    def save_report(self, output_file: str = None):
        """Save report to JSON file"""
        if not output_file:
            output_file = f"reuse_check_{self.component_name}.json"

        output_path = Path(__file__).parent / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\nReport saved to: {output_path}")

    def log_to_evolution_system(self):
        """Log check results to evolution system for pattern analysis"""
        try:
            evolution_dir = Path(__file__).parent.parent / "evolution"
            reuse_log_path = evolution_dir / "reuse_log.json"

            # Load existing log
            if reuse_log_path.exists():
                with open(reuse_log_path, "r", encoding="utf-8") as f:
                    reuse_log = json.load(f)
            else:
                reuse_log = {
                    "description": "Tracks code reuse checks",
                    "version": "1.0",
                    "checks": [],
                    "statistics": {
                        "total_checks": 0,
                        "duplicates_prevented": 0,
                        "antipatterns_caught": 0,
                        "most_common_antipatterns": {},
                        "reuse_rate": 0.0,
                    },
                    "patterns": {"frequently_requested": [], "should_be_in_docs": []},
                }

            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "component_name": self.component_name,
                "interface_name": self.interface_name,
                "result": self.results["severity"].lower(),
                "duplicates_found": len(self.results["duplicate_components"]),
                "antipatterns_detected": len(self.results["anti_patterns"]),
                "suggested_libraries": self.results["suggested_libraries"],
                "action_taken": "proceeded"
                if self.results["severity"] == "OK"
                else "review_required",
                "notes": ", ".join(self.results["warnings"])
                if self.results["warnings"]
                else "No issues",
            }

            # Add to log
            reuse_log["checks"].append(log_entry)

            # Update statistics
            stats = reuse_log["statistics"]
            stats["total_checks"] = len(reuse_log["checks"])

            if self.results["severity"] == "CRITICAL":
                stats["duplicates_prevented"] += 1

            if self.results["anti_patterns"]:
                stats["antipatterns_caught"] += 1
                for ap in self.results["anti_patterns"]:
                    pattern_name = ap["pattern"]
                    stats["most_common_antipatterns"][pattern_name] = (
                        stats["most_common_antipatterns"].get(pattern_name, 0) + 1
                    )

            # Calculate reuse rate
            if stats["total_checks"] > 0:
                prevented = stats["duplicates_prevented"] + stats["antipatterns_caught"]
                stats["reuse_rate"] = prevented / stats["total_checks"]

            # Track frequently requested components
            component_counts = {}
            for check in reuse_log["checks"]:
                comp = check["component_name"]
                component_counts[comp] = component_counts.get(comp, 0) + 1

            # Find components requested multiple times (might need docs)
            frequent = [
                (comp, count) for comp, count in component_counts.items() if count >= 2
            ]
            frequent.sort(key=lambda x: x[1], reverse=True)
            reuse_log["patterns"]["frequently_requested"] = [
                {"component": comp, "count": count} for comp, count in frequent[:10]
            ]

            # Save updated log
            with open(reuse_log_path, "w", encoding="utf-8") as f:
                json.dump(reuse_log, f, indent=2, ensure_ascii=False)

            print(f"\n[Evolution] Logged to reuse tracking system")
            print(f"  Total checks: {stats['total_checks']}")
            print(f"  Duplicates prevented: {stats['duplicates_prevented']}")
            print(f"  Anti-patterns caught: {stats['antipatterns_caught']}")
            print(f"  Reuse rate: {stats['reuse_rate']:.1%}")

        except Exception as e:
            print(f"\n[Warning] Could not log to evolution system: {e}")
            # Continue anyway - logging failure shouldn't break the tool

    def run(self) -> int:
        """Run all checks and return exit code"""
        print("=" * 50)
        print("Code Reuse Analysis")
        print("=" * 50)
        print()

        self.check_duplicate_components()
        self.check_duplicate_interfaces()
        self.check_caa_samples()
        self.check_anti_patterns()
        self.analyze_functionality()
        self.generate_report()

        # Log to evolution system
        self.log_to_evolution_system()

        # Return exit code based on severity
        if self.results["severity"] == "CRITICAL":
            return 2
        elif self.results["severity"] == "WARNING":
            return 1
        else:
            return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: check_code_reuse.py <ComponentName> [InterfaceName] [WorkspacePath]")
        print("Example: check_code_reuse.py Calculator ICalculator")
        sys.exit(1)

    component_name = sys.argv[1]
    interface_name = sys.argv[2] if len(sys.argv) > 2 else None
    workspace_override = sys.argv[3] if len(sys.argv) > 3 else None
    if workspace_override:
        global WORKSPACE, CAA_SYSTEM_PATH
        WORKSPACE = workspace_override
        CAA_SYSTEM_PATH = os.path.join(WORKSPACE, "CAASystem.edu")

    checker = CodeReuseChecker(component_name, interface_name)
    exit_code = checker.run()

    # Save report
    checker.save_report()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

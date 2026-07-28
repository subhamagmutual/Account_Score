"""
Feature Importance Analysis for Composite Score Model
======================================================

Analyzes which variables drive the composite score most, identifies dead weight,
and recommends optimization/simplification.

Works with the hierarchical weighted-average formula:
- Composite = SUM(W_component * component_i * I_i) / SUM(W_component * I_i)
- Component = SUM(W_variable * variable_j * I_j) / SUM(W_variable * I_j)

Provides:
1. Sensitivity analysis (±10%, ±25%, ±50% changes)
2. Structural importance ranking
3. Weight efficiency assessment
4. Simplification recommendations
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import json


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class VariableConfig:
    """Single variable within a component."""
    name: str
    weight: float
    component: str


@dataclass
class ComponentConfig:
    """Single component within composite."""
    name: str
    weight: float
    variables: Dict[str, VariableConfig]


@dataclass
class CompositeConfig:
    """Full model configuration."""
    components: Dict[str, ComponentConfig]
    composite_weights: Dict[str, float]


# ============================================================================
# CONFIGURATION (from scoring_logic_summary.txt)
# ============================================================================

def build_config() -> CompositeConfig:
    """Build the model configuration from scoring logic."""
    
    # Composite-level weights
    composite_weights = {
        "adequacy": 0.40,
        "capacity": 0.25,
        "appetite": 0.25,
        "environment": 0.10
    }
    
    # Component-level variable weights
    adequacy_vars = {
        "total_loss_cost": 0.20,
        "indemnity_loss_cost": 0.10,
        "expense_loss_cost": 0.05,
        "total_frequency": 0.10,
        "indemnity_frequency": 0.05,
        "total_severity": 0.05,
        "actual_loss_ratio": 0.10,
        "loss_free_years": 0.10,
        "limits_to_premium": 0.10,
    }
    
    capacity_vars = {
        "per_occurrence_limit": 0.20,
        "aggregate_limit": 0.10,
        "risk_count": 0.10,
    }
    
    appetite_vars = {
        "specialty_risk_tier": 0.25,
        "state_venue_risk": 0.15,
        "years_since_graduation": 0.10,
        "rvu_ratio": 0.10,
        "tenure_with_carrier": 0.05,
        "hospital_rating": 0.05,
        "practice_size": 0.05,
    }
    
    environment_vars = {
        "income_inequality": 0.05,
        "population_density": 0.05,
        "violent_crime_rate": 0.03,
        "pct_uninsured": 0.02,
    }
    
    # Build component objects
    components = {
        "adequacy": ComponentConfig(
            name="adequacy",
            weight=composite_weights["adequacy"],
            variables={k: VariableConfig(k, v, "adequacy") for k, v in adequacy_vars.items()}
        ),
        "capacity": ComponentConfig(
            name="capacity",
            weight=composite_weights["capacity"],
            variables={k: VariableConfig(k, v, "capacity") for k, v in capacity_vars.items()}
        ),
        "appetite": ComponentConfig(
            name="appetite",
            weight=composite_weights["appetite"],
            variables={k: VariableConfig(k, v, "appetite") for k, v in appetite_vars.items()}
        ),
        "environment": ComponentConfig(
            name="environment",
            weight=composite_weights["environment"],
            variables={k: VariableConfig(k, v, "environment") for k, v in environment_vars.items()}
        ),
    }
    
    return CompositeConfig(components=components, composite_weights=composite_weights)


# ============================================================================
# SENSITIVITY ANALYSIS
# ============================================================================

def weighted_average(values: Dict[str, float], weights: Dict[str, float]) -> float:
    """
    Compute weighted average with weight-zeroing.
    Missing values (NaN) zero out their weight.
    """
    total_weighted = 0.0
    total_active_weight = 0.0
    
    for key, value in values.items():
        if key in weights and pd.notna(value):
            w = weights[key]
            total_weighted += value * w
            total_active_weight += w
    
    if total_active_weight == 0:
        return np.nan
    
    return total_weighted / total_active_weight


def compute_composite(adequacy: float, capacity: float, appetite: float, 
                     environment: float, weights: Dict[str, float]) -> float:
    """Compute composite score from component scores."""
    components = {
        "adequacy": adequacy,
        "capacity": capacity,
        "appetite": appetite,
        "environment": environment
    }
    return weighted_average(components, weights)


class SensitivityAnalyzer:
    """Performs sensitivity analysis on the scoring model."""
    
    def __init__(self, config: CompositeConfig):
        self.config = config
        self.baseline = self._baseline_scenario()
    
    def _baseline_scenario(self) -> Dict[str, float]:
        """Baseline: all scores at 5 (portfolio average)."""
        return {
            "adequacy": 5.0,
            "capacity": 5.0,
            "appetite": 5.0,
            "environment": 5.0,
        }
    
    def baseline_composite(self) -> float:
        """Compute composite at baseline (all components = 5)."""
        return compute_composite(
            self.baseline["adequacy"],
            self.baseline["capacity"],
            self.baseline["appetite"],
            self.baseline["environment"],
            self.config.composite_weights
        )
    
    def sensitivity_to_component_change(self, component_name: str, pct_change: float) -> float:
        """
        Sensitivity: if {component_name} changes by {pct_change}%, 
        what's the new composite?
        
        Args:
            component_name: "adequacy", "capacity", "appetite", "environment"
            pct_change: percentage change (e.g., 10 for +10%, -10 for -10%)
        
        Returns:
            New composite score
        """
        scenario = self.baseline.copy()
        baseline_value = scenario[component_name]
        scenario[component_name] = baseline_value * (1 + pct_change / 100)
        
        return compute_composite(
            scenario["adequacy"],
            scenario["capacity"],
            scenario["appetite"],
            scenario["environment"],
            self.config.composite_weights
        )
    
    def component_impact_matrix(self) -> pd.DataFrame:
        """
        Sensitivity matrix: how much does composite change for each component?
        
        Rows: components
        Cols: percentage changes (-50%, -25%, -10%, +10%, +25%, +50%)
        """
        changes = [-50, -25, -10, 10, 25, 50]
        components = list(self.config.components.keys())
        
        matrix = {}
        baseline = self.baseline_composite()
        
        for pct in changes:
            col_data = {}
            for comp in components:
                new_composite = self.sensitivity_to_component_change(comp, pct)
                delta = new_composite - baseline
                col_data[comp] = delta
            matrix[f"{pct:+d}%"] = col_data
        
        df = pd.DataFrame(matrix).T
        return df[components]  # Reorder
    
    def component_elasticity(self) -> Dict[str, float]:
        """
        Elasticity: % change in composite per 1% change in component.
        Higher = more sensitive.
        """
        baseline = self.baseline_composite()
        elasticity = {}
        
        for comp in self.config.components.keys():
            new_comp = self.sensitivity_to_component_change(comp, 1.0)  # +1%
            delta_pct = ((new_comp - baseline) / baseline) * 100
            elasticity[comp] = delta_pct
        
        return elasticity
    
    def variable_structural_importance(self) -> Dict[str, Dict[str, Any]]:
        """
        Structural importance: based on weights and nesting.
        
        Each variable's importance = 
            weight_in_component * weight_of_component
        
        This captures direct impact if a variable moves.
        """
        importance = {}
        
        for comp_name, comp in self.config.components.items():
            for var_name, var in comp.variables.items():
                # Direct effect: var weight × component weight
                direct_effect = var.weight * comp.weight
                
                importance[var_name] = {
                    "component": comp_name,
                    "variable_weight": var.weight,
                    "component_weight": comp.weight,
                    "direct_effect": direct_effect,
                    "rank": None  # Will be filled after sorting
                }
        
        # Rank by direct effect
        ranked = sorted(importance.items(), key=lambda x: x[1]["direct_effect"], reverse=True)
        for rank, (var_name, data) in enumerate(ranked, 1):
            importance[var_name]["rank"] = rank
        
        return importance


# ============================================================================
# OPTIMIZATION ANALYSIS
# ============================================================================

class OptimizationAnalyzer:
    """Identifies opportunities to simplify and optimize the model."""
    
    def __init__(self, config: CompositeConfig, sensitivity: SensitivityAnalyzer):
        self.config = config
        self.sensitivity = sensitivity
        self.var_importance = sensitivity.variable_structural_importance()
    
    def dead_weight_detection(self, threshold_pct: float = 1.0) -> Dict[str, List[str]]:
        """
        Identify low-impact variables.
        
        A variable is "dead weight" if its contribution < threshold_pct of total importance.
        
        Args:
            threshold_pct: importance threshold (default 1% of total)
        
        Returns:
            Dict mapping component -> list of dead-weight variables
        """
        total_importance = sum(v["direct_effect"] for v in self.var_importance.values())
        threshold = (threshold_pct / 100) * total_importance
        
        dead_weight = {}
        for comp in self.config.components.keys():
            dead_weight[comp] = []
        
        for var_name, data in self.var_importance.items():
            if data["direct_effect"] < threshold:
                comp = data["component"]
                dead_weight[comp].append(var_name)
        
        return dead_weight
    
    def component_contribution_analysis(self) -> Dict[str, Dict[str, Any]]:
        """
        For each component, analyze:
        - Its weight in composite
        - Number of variables
        - Average variable weight
        - Total variance it could contribute
        """
        analysis = {}
        
        for comp_name, comp in self.config.components.items():
            var_count = len(comp.variables)
            var_weights = [v.weight for v in comp.variables.values()]
            
            analysis[comp_name] = {
                "composite_weight": comp.weight,
                "variable_count": var_count,
                "avg_variable_weight": np.mean(var_weights),
                "total_variable_weight": sum(var_weights),
                "max_variable_weight": max(var_weights) if var_weights else 0,
                "min_variable_weight": min(var_weights) if var_weights else 0,
            }
        
        return analysis
    
    def simplification_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """
        Test hypothetical simplifications:
        - Drop lowest-weight variables
        - Combine components
        - Uniform weighting within component
        """
        scenarios = {}
        
        # Scenario 1: Drop all variables <1% importance
        dead = self.dead_weight_detection(threshold_pct=1.0)
        scenarios["drop_dead_weight"] = {
            "description": "Remove variables with <1% importance",
            "variables_removed": sum(len(v) for v in dead.values()),
            "by_component": dead,
        }
        
        # Scenario 2: Consolidate to 3 components (drop Environment)
        # Redistribute Environment weight to others proportionally
        base_3 = 0.40 + 0.25 + 0.25  # Sum of 3 largest
        scenarios["drop_environment"] = {
            "description": "Drop Environment (10%), redistribute weight proportionally",
            "new_weights": {
                "adequacy": 0.40 / base_3 * (base_3 + 0.10),
                "capacity": 0.25 / base_3 * (base_3 + 0.10),
                "appetite": 0.25 / base_3 * (base_3 + 0.10),
            },
            "note": "Weights normalized to sum to 1.0"
        }
        
        # Scenario 3: Uniform weighting within each component
        scenarios["uniform_within_component"] = {
            "description": "Equal weight for all variables within each component",
            "by_component": {
                comp: f"1/{len(comp_obj.variables)} for each variable"
                for comp, comp_obj in self.config.components.items()
            }
        }
        
        return scenarios


# ============================================================================
# REPORTING
# ============================================================================

def print_section(title: str, width: int = 80):
    """Print a formatted section header."""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_subsection(title: str, width: int = 80):
    """Print a formatted subsection header."""
    print(f"\n{title}")
    print("-" * len(title))


class FeatureImportanceReport:
    """Generates comprehensive importance analysis report."""
    
    def __init__(self, config: CompositeConfig):
        self.config = config
        self.sensitivity = SensitivityAnalyzer(config)
        self.optimizer = OptimizationAnalyzer(config, self.sensitivity)
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """Run complete analysis and return results."""
        results = {
            "baseline_composite": self.sensitivity.baseline_composite(),
            "component_elasticity": self.sensitivity.component_elasticity(),
            "component_impact_matrix": self.sensitivity.component_impact_matrix(),
            "variable_importance": self.sensitivity.variable_structural_importance(),
            "dead_weight": self.optimizer.dead_weight_detection(),
            "component_analysis": self.optimizer.component_contribution_analysis(),
            "simplification_scenarios": self.optimizer.simplification_scenarios(),
        }
        return results
    
    def print_report(self):
        """Print human-readable analysis report."""
        
        print_section("FEATURE IMPORTANCE ANALYSIS - COMPOSITE SCORE MODEL")
        
        # ---- Baseline ----
        print_subsection("1. BASELINE SCENARIO")
        baseline = self.sensitivity.baseline_composite()
        print(f"All components at 5.0 (portfolio average)")
        print(f"Baseline composite score: {baseline:.2f}")
        
        # ---- Component Elasticity ----
        print_subsection("2. COMPONENT SENSITIVITY (Elasticity)")
        print("How much (%) does composite change per 1% change in each component?")
        print()
        elasticity = self.sensitivity.component_elasticity()
        elasticity_df = pd.DataFrame(list(elasticity.items()), 
                                     columns=["Component", "Elasticity (%/%)"])
        elasticity_df = elasticity_df.sort_values("Elasticity (%/%)", ascending=False)
        print(elasticity_df.to_string(index=False))
        print()
        print("→ Adequacy dominates: 1% change in Adequacy = {:.2f}% change in Composite".format(
            elasticity["adequacy"]))
        
        # ---- Impact Matrix ----
        print_subsection("3. COMPONENT IMPACT MATRIX")
        print("Absolute change in composite score for ±10%, ±25%, ±50% changes:")
        print()
        impact = self.sensitivity.component_impact_matrix()
        print(impact.round(3).to_string())
        print()
        
        # ---- Variable Importance Ranking ----
        print_subsection("4. VARIABLE STRUCTURAL IMPORTANCE RANKING")
        var_imp = self.sensitivity.variable_structural_importance()
        var_df = pd.DataFrame([
            {
                "Rank": v["rank"],
                "Variable": k,
                "Component": v["component"],
                "Var Weight": f"{v['variable_weight']:.2f}",
                "Comp Weight": f"{v['component_weight']:.2f}",
                "Direct Effect": f"{v['direct_effect']:.4f}"
            }
            for k, v in var_imp.items()
        ]).sort_values("Rank")
        
        print(var_df.to_string(index=False))
        print()
        
        # ---- Dead Weight Detection ----
        print_subsection("5. DEAD WEIGHT DETECTION")
        dead = self.optimizer.dead_weight_detection(threshold_pct=1.0)
        print("Variables with <1% importance (candidates for removal):")
        print()
        
        total_dead = 0
        for comp, vars in dead.items():
            if vars:
                print(f"  {comp.upper()}: {', '.join(vars)}")
                total_dead += len(vars)
        
        if total_dead == 0:
            print("  (None found)")
        else:
            print(f"\n  Total: {total_dead} variables could be simplified")
        print()
        
        # ---- Component Analysis ----
        print_subsection("6. COMPONENT EFFICIENCY ANALYSIS")
        comp_analysis = self.optimizer.component_contribution_analysis()
        comp_df = pd.DataFrame([
            {
                "Component": comp,
                "Weight (%)": f"{data['composite_weight']*100:.1f}%",
                "# Variables": data['variable_count'],
                "Avg Var Wt": f"{data['avg_variable_weight']:.3f}",
                "Max Var Wt": f"{data['max_variable_weight']:.3f}",
                "Min Var Wt": f"{data['min_variable_weight']:.3f}",
            }
            for comp, data in comp_analysis.items()
        ])
        print(comp_df.to_string(index=False))
        print()
        print("→ Adequacy (40%) has 9 variables; Environment (10%) has 4")
        print("→ Variable weights vary widely (0.02 to 0.25)")
        print()
        
        # ---- Simplification Scenarios ----
        print_subsection("7. SIMPLIFICATION RECOMMENDATIONS")
        scenarios = self.optimizer.simplification_scenarios()
        
        print("SCENARIO A: Drop dead-weight variables (<1% importance)")
        print(f"  Variables to remove: {scenarios['drop_dead_weight']['variables_removed']}")
        print("  Impact: Minimal - these variables barely move the score")
        print("  Effort: Low - just remove from config")
        print()
        
        print("SCENARIO B: Consolidate to 3 components (drop Environment)")
        print("  Current: Adequacy (40%) + Capacity (25%) + Appetite (25%) + Environment (10%)")
        print("  Proposed: Keep top 3, redistribute Environment weight")
        print("  Impact: Medium - Environment contributes only 10%, but affects ~4 variables")
        print("  Effort: Medium - requires reweighting")
        print()
        
        print("SCENARIO C: Uniform weights within components")
        print("  Current: Weights vary (e.g., Adequacy: 0.05-0.20)")
        print("  Proposed: Equal weight for all variables in each component")
        print("  Impact: Low to Medium - simplifies logic, may slightly reduce discrimination")
        print("  Effort: Low - mechanical change to config")
        print()
        
        # ---- Key Findings ----
        print_subsection("KEY FINDINGS & RECOMMENDATIONS")
        print("""
1. ADEQUACY DOMINATES (40% weight)
   - Controls ~40% of composite score directly
   - 9 variables with varied weights (0.05-0.20)
   - Focus here for model tuning

2. CAPACITY & APPETITE ARE EQUALLY IMPORTANT (25% each)
   - Capacity has only 3 variables (more weight per variable)
   - Appetite has 7 variables (more distributed)

3. ENVIRONMENT IS UNDERUTILIZED (10% weight)
   - Smallest component with 4 variables
   - Each variable has very low weight (0.02-0.05)
   - Candidate for consolidation or removal

4. RECOMMENDED QUICK WINS:
   ✓ Drop 1-2 dead-weight variables (see Section 5)
   ✓ Verify specialty_risk_tier & state_venue_risk (highest impact in Appetite)
   ✓ Consider dropping Environment entirely, redistribute its 10% weight

5. FOR DATA-DRIVEN OPTIMIZATION:
   - Collect real data on actual scores
   - Measure real variance in each variable
   - Check correlation with actual outcomes
   - Re-weight based on predictive power (not just logic)
        """)
    
    def export_to_excel(self, filepath: str):
        """Export analysis to Excel workbook with multiple sheets."""
        results = self.run_full_analysis()
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Summary
            summary_data = {
                "Metric": [
                    "Baseline Composite (all=5.0)",
                    "Elasticity - Adequacy",
                    "Elasticity - Capacity",
                    "Elasticity - Appetite",
                    "Elasticity - Environment",
                ],
                "Value": [
                    f"{results['baseline_composite']:.2f}",
                    f"{results['component_elasticity']['adequacy']:.4f}",
                    f"{results['component_elasticity']['capacity']:.4f}",
                    f"{results['component_elasticity']['appetite']:.4f}",
                    f"{results['component_elasticity']['environment']:.4f}",
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)
            
            # Component Impact Matrix
            results['component_impact_matrix'].to_excel(writer, sheet_name="Impact Matrix")
            
            # Variable Importance
            var_df = pd.DataFrame([
                {
                    "Rank": v["rank"],
                    "Variable": k,
                    "Component": v["component"],
                    "Variable_Weight": v['variable_weight'],
                    "Component_Weight": v['component_weight'],
                    "Direct_Effect": v['direct_effect'],
                }
                for k, v in results['variable_importance'].items()
            ]).sort_values("Rank")
            var_df.to_excel(writer, sheet_name="Variable Importance", index=False)
            
            # Component Analysis
            comp_df = pd.DataFrame(
                [(k, v) for k, v in results['component_analysis'].items()]
            )
            comp_df.to_excel(writer, sheet_name="Component Analysis", index=False)
            
            # Dead Weight
            dead_df_rows = []
            for comp, vars in results['dead_weight'].items():
                for var in vars:
                    dead_df_rows.append({"Component": comp, "Variable": var})
            if dead_df_rows:
                pd.DataFrame(dead_df_rows).to_excel(writer, sheet_name="Dead Weight", index=False)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run full feature importance analysis."""
    
    print("\n")
    print("█" * 80)
    print("█  FEATURE IMPORTANCE ANALYSIS - COMPOSITE SCORE MODEL")
    print("█" * 80)
    
    # Build configuration
    config = build_config()
    
    # Run analysis and print report
    report = FeatureImportanceReport(config)
    report.print_report()
    
    # Export to Excel
    excel_path = "feature_importance_analysis.xlsx"
    report.export_to_excel(excel_path)
    print_section("EXPORT")
    print(f"✓ Analysis exported to: {excel_path}")
    
    # Export raw JSON for programmatic use
    results = report.run_full_analysis()
    
    # Convert to JSON-serializable format
    results_json = {
        "baseline_composite": float(results['baseline_composite']),
        "component_elasticity": {k: float(v) for k, v in results['component_elasticity'].items()},
        "component_impact_matrix": results['component_impact_matrix'].to_dict(),
        "variable_importance": {
            k: {**v, "direct_effect": float(v["direct_effect"]), "variable_weight": float(v["variable_weight"]), "component_weight": float(v["component_weight"])}
            for k, v in results['variable_importance'].items()
        },
        "dead_weight": results['dead_weight'],
        "component_analysis": {
            k: {k2: float(v2) if isinstance(v2, (int, float)) else v2 for k2, v2 in v.items()}
            for k, v in results['component_analysis'].items()
        },
    }
    
    with open("feature_importance_analysis.json", "w") as f:
        json.dump(results_json, f, indent=2)
    
    print(f"✓ Raw results exported to: feature_importance_analysis.json")
    print()


if __name__ == "__main__":
    main()

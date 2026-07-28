"""Dashboard and reporting - generate performance reports."""

from typing import Dict, List, Optional
from datetime import datetime
import json
import pandas as pd


class DashboardGenerator:
    """Generate performance dashboards and reports."""

    def __init__(self):
        """Initialize dashboard generator."""
        self.reports = {}

    def generate_performance_dashboard(
        self,
        df: pd.DataFrame,
        score_column: str,
        loss_column: str,
        component_columns: List[str],
    ) -> Dict:
        """
        Generate comprehensive performance dashboard.

        Args:
            df: Scored dataframe
            score_column: Composite score column
            loss_column: Loss column
            component_columns: Component score columns

        Returns:
            Dashboard data
        """
        from scipy import stats

        dashboard = {
            'generated_at': datetime.utcnow().isoformat(),
            'total_records': len(df),
            'valid_records': len(df[score_column].dropna()),
        }

        # 1. Score distribution
        scores = df[score_column].dropna()
        dashboard['score_distribution'] = {
            'mean': float(scores.mean()),
            'median': float(scores.median()),
            'std': float(scores.std()),
            'min': float(scores.min()),
            'max': float(scores.max()),
            'p10': float(scores.quantile(0.10)),
            'p25': float(scores.quantile(0.25)),
            'p75': float(scores.quantile(0.75)),
            'p90': float(scores.quantile(0.90)),
        }

        # 2. Discrimination (correlation to loss)
        valid_data = df[[score_column, loss_column]].dropna()
        if len(valid_data) > 2:
            spearman, p_val = stats.spearmanr(valid_data[score_column], valid_data[loss_column])
            dashboard['discrimination'] = {
                'correlation': float(spearman),
                'pvalue': float(p_val),
                'significant': p_val < 0.05,
            }

        # 3. Component scores
        dashboard['components'] = {}
        for comp_col in component_columns:
            if comp_col in df.columns:
                comp_scores = df[comp_col].dropna()
                dashboard['components'][comp_col] = {
                    'mean': float(comp_scores.mean()),
                    'std': float(comp_scores.std()),
                    'count': len(comp_scores),
                }

        # 4. Risk distribution
        dashboard['risk_distribution'] = {
            'low': int((scores < 4).sum()),
            'medium': int(((scores >= 4) & (scores < 7)).sum()),
            'high': int((scores >= 7).sum()),
        }

        self.reports['performance'] = dashboard
        return dashboard

    def generate_model_comparison_dashboard(
        self,
        model_results: Dict[str, Dict],
    ) -> Dict:
        """
        Compare multiple model versions.

        Args:
            model_results: Dict of model_name -> metrics

        Returns:
            Comparison dashboard
        """
        dashboard = {
            'generated_at': datetime.utcnow().isoformat(),
            'models': model_results,
            'comparison': self._rank_models(model_results),
        }

        self.reports['comparison'] = dashboard
        return dashboard

    def generate_population_dashboard(
        self,
        population_stats: Dict[str, Dict],
    ) -> Dict:
        """
        Dashboard for population analysis.

        Args:
            population_stats: Stats by population

        Returns:
            Population dashboard
        """
        dashboard = {
            'generated_at': datetime.utcnow().isoformat(),
            'populations': population_stats,
            'summary': {
                'total_populations': len(population_stats),
                'total_records': sum(v.get('count', 0) for v in population_stats.values()),
            },
        }

        self.reports['population'] = dashboard
        return dashboard

    def export_dashboard_html(
        self,
        dashboard_data: Dict,
        output_path: str,
    ):
        """
        Export dashboard as HTML report.

        Args:
            dashboard_data: Dashboard data dict
            output_path: Output file path
        """
        html = self._build_html_dashboard(dashboard_data)

        with open(output_path, 'w') as f:
            f.write(html)

    def export_dashboard_json(
        self,
        dashboard_data: Dict,
        output_path: str,
    ):
        """
        Export dashboard as JSON.

        Args:
            dashboard_data: Dashboard data dict
            output_path: Output file path
        """
        with open(output_path, 'w') as f:
            json.dump(dashboard_data, f, indent=2, default=str)

    @staticmethod
    def _rank_models(model_results: Dict[str, Dict]) -> List[Dict]:
        """Rank models by performance metrics."""
        ranked = []

        for model_name, metrics in model_results.items():
            score = metrics.get('discrimination', {}).get('correlation', 0) * 100
            ranked.append({
                'model': model_name,
                'discrimination_score': float(score),
                'metrics': metrics,
            })

        return sorted(ranked, key=lambda x: x['discrimination_score'], reverse=True)

    @staticmethod
    def _build_html_dashboard(dashboard_data: Dict) -> str:
        """Build HTML dashboard."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>PAS Performance Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                .metric { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
                .metric-value { font-size: 24px; font-weight: bold; color: #0066cc; }
                .metric-label { font-size: 12px; color: #666; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background: #0066cc; color: white; }
            </style>
        </head>
        <body>
            <h1>PAS Performance Dashboard</h1>
            <p>Generated: {timestamp}</p>
        """.format(timestamp=dashboard_data.get('generated_at', 'N/A'))

        # Add metrics
        if 'score_distribution' in dashboard_data:
            dist = dashboard_data['score_distribution']
            html += f"""
            <div class="metric">
                <div class="metric-label">Average Score</div>
                <div class="metric-value">{dist['mean']:.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Score Range</div>
                <div class="metric-value">{dist['min']:.1f} - {dist['max']:.1f}</div>
            </div>
            """

        html += """
        </body>
        </html>
        """

        return html

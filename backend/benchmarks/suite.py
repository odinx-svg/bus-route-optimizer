"""
Suite de benchmarks para algoritmos de optimización.
"""

import time
import json
import statistics
from typing import List, Dict, Callable, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

try:
    from backend.models import Route, BusSchedule
    from backend.validation.monte_carlo import MonteCarloValidator, estimate_base_travel_times
except ImportError:
    from models import Route, BusSchedule
    from validation.monte_carlo import MonteCarloValidator, estimate_base_travel_times


@dataclass
class BenchmarkResult:
    """Resultado de benchmark."""
    algorithm: str
    dataset: str
    n_routes: int
    execution_time_ms: float
    n_buses: int
    total_km: float
    deadhead_km: float
    avg_routes_per_bus: float
    objective_score: float
    robustness_grade: Optional[str] = None
    feasibility_rate: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convertir a diccionario."""
        return asdict(self)
    
    def __repr__(self) -> str:
        return (f"BenchmarkResult({self.algorithm} on {self.dataset}: "
                f"{self.n_buses} buses, {self.execution_time_ms:.0f}ms, "
                f"score={self.objective_score:.2f})")


class BenchmarkSuite:
    """Suite de benchmarks para algoritmos de optimización."""
    
    def __init__(self, output_dir: str = "benchmarks/results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[BenchmarkResult] = []
    
    def run_benchmark(
        self,
        algorithm: Callable[[List[Route]], List[BusSchedule]],
        algorithm_name: str,
        dataset: List[Route],
        dataset_name: str,
        evaluator: Optional[Callable[[List[BusSchedule], List[Route]], float]] = None,
        n_runs: int = 5,
        validate_robustness: bool = True
    ) -> BenchmarkResult:
        """
        Ejecutar benchmark de un algoritmo.
        
        Args:
            algorithm: Función de optimización a testear
            algorithm_name: Nombre del algoritmo
            dataset: Dataset de rutas
            dataset_name: Nombre del dataset
            evaluator: Función que evalúa la calidad (schedule, routes) -> score
            n_runs: Número de ejecuciones (para promedio)
            validate_robustness: Si validar robustez con Monte Carlo
        """
        times = []
        scores = []
        best_schedule = None
        best_score = float('inf')
        
        for run in range(n_runs):
            start = time.time()
            try:
                schedule = algorithm(dataset)
                elapsed = (time.time() - start) * 1000  # ms
                
                if evaluator:
                    score = evaluator(schedule, dataset)
                else:
                    score = self._default_evaluator(schedule, dataset)
                
                times.append(elapsed)
                scores.append(score)
                
                if score < best_score:
                    best_score = score
                    best_schedule = schedule
                    
            except Exception as e:
                print(f"  ERROR en run {run + 1}: {e}")
                continue
        
        if not times:
            raise RuntimeError(f"Algoritmo {algorithm_name} falló en todos los runs")
        
        # Calcular métricas de robustez si se solicita
        robustness_grade = None
        feasibility_rate = None
        if validate_robustness and best_schedule:
            try:
                validator = MonteCarloValidator(n_simulations=100, seed=42)
                base_times = estimate_base_travel_times(dataset)
                mc_result = validator.validate_schedule(best_schedule, base_times)
                robustness_grade = validator.get_robustness_grade(mc_result)
                feasibility_rate = mc_result.feasibility_rate
            except Exception as e:
                print(f"  WARNING: No se pudo validar robustez: {e}")
        
        # Calcular métricas
        result = BenchmarkResult(
            algorithm=algorithm_name,
            dataset=dataset_name,
            n_routes=len(dataset),
            execution_time_ms=statistics.mean(times),
            n_buses=len(best_schedule) if best_schedule else 0,
            total_km=self.calculate_total_km(best_schedule),
            deadhead_km=self.calculate_deadhead(best_schedule),
            avg_routes_per_bus=self._calculate_avg_routes_per_bus(best_schedule),
            objective_score=best_score,
            robustness_grade=robustness_grade,
            feasibility_rate=feasibility_rate,
            timestamp=datetime.now().isoformat(),
            metadata={
                "time_std": statistics.stdev(times) if len(times) > 1 else 0,
                "time_min": min(times),
                "time_max": max(times),
                "score_std": statistics.stdev(scores) if len(scores) > 1 else 0,
                "score_min": min(scores),
                "score_max": max(scores),
                "n_runs": len(times),
                "failed_runs": n_runs - len(times)
            }
        )
        
        self.results.append(result)
        return result
    
    def compare_algorithms(
        self,
        results: Optional[List[BenchmarkResult]] = None,
        baseline_index: int = 0
    ) -> Dict:
        """
        Comparar resultados de múltiples algoritmos.
        
        Args:
            results: Lista de resultados a comparar (usa self.results si None)
            baseline_index: Índice del algoritmo baseline
        
        Returns:
            Dict con análisis comparativo
        """
        if results is None:
            results = self.results
        
        if not results:
            return {}
        
        if baseline_index >= len(results):
            baseline_index = 0
        
        baseline = results[baseline_index]
        
        comparison = {
            "baseline": baseline.algorithm,
            "dataset": baseline.dataset,
            "n_routes": baseline.n_routes,
            "baseline_metrics": {
                "buses": baseline.n_buses,
                "deadhead_km": baseline.deadhead_km,
                "execution_time_ms": baseline.execution_time_ms,
                "objective_score": baseline.objective_score,
                "robustness_grade": baseline.robustness_grade
            },
            "comparisons": [],
            "summary": {
                "best_algorithm": None,
                "improvements_over_baseline": []
            }
        }
        
        best_score = baseline.objective_score
        best_algo = baseline.algorithm
        
        for i, result in enumerate(results):
            if i == baseline_index:
                continue
            
            # Calcular mejoras porcentuales
            bus_diff_pct = (result.n_buses - baseline.n_buses) / baseline.n_buses * 100
            deadhead_diff_pct = (result.deadhead_km - baseline.deadhead_km) / baseline.deadhead_km * 100 if baseline.deadhead_km > 0 else 0
            time_diff_pct = (result.execution_time_ms - baseline.execution_time_ms) / baseline.execution_time_ms * 100
            score_diff_pct = (result.objective_score - baseline.objective_score) / baseline.objective_score * 100 if baseline.objective_score > 0 else 0
            
            comp = {
                "algorithm": result.algorithm,
                "vs_baseline": {
                    "buses": f"{bus_diff_pct:+.1f}%",
                    "buses_saved": baseline.n_buses - result.n_buses,
                    "deadhead": f"{deadhead_diff_pct:+.1f}%",
                    "time": f"{time_diff_pct:+.1f}%",
                    "objective": f"{score_diff_pct:+.1f}%"
                },
                "absolute_metrics": {
                    "buses": result.n_buses,
                    "deadhead_km": result.deadhead_km,
                    "execution_time_ms": result.execution_time_ms,
                    "objective_score": result.objective_score,
                    "robustness_grade": result.robustness_grade
                },
                "winner": self._determine_winner(result, baseline)
            }
            comparison["comparisons"].append(comp)
            
            # Track best
            if result.objective_score < best_score:
                best_score = result.objective_score
                best_algo = result.algorithm
        
        comparison["summary"]["best_algorithm"] = best_algo
        
        return comparison
    
    def generate_report(self, filename: Optional[str] = None) -> str:
        """
        Generar reporte completo de benchmarks.
        
        Args:
            filename: Nombre del archivo (auto-generado si None)
        
        Returns:
            Ruta al archivo generado
        """
        if filename is None:
            filename = f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.output_dir / filename
        
        # Agrupar resultados por dataset
        by_dataset: Dict[str, List[BenchmarkResult]] = {}
        for result in self.results:
            if result.dataset not in by_dataset:
                by_dataset[result.dataset] = []
            by_dataset[result.dataset].append(result)
        
        # Generar comparaciones por dataset
        dataset_comparisons = {}
        for dataset, results in by_dataset.items():
            if len(results) > 1:
                dataset_comparisons[dataset] = self.compare_algorithms(results)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_benchmarks": len(self.results),
                "datasets_tested": list(by_dataset.keys()),
                "algorithms_tested": list(set(r.algorithm for r in self.results))
            },
            "results_by_dataset": {
                dataset: [r.to_dict() for r in results]
                for dataset, results in by_dataset.items()
            },
            "comparisons": dataset_comparisons,
            "all_results": [r.to_dict() for r in self.results]
        }
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)
        
        return str(filepath)
    
    def save_results(self, filename: str = None):
        """Guardar resultados a JSON (formato simple)."""
        if filename is None:
            filename = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results]
        }
        
        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        return str(filepath)
    
    def load_results(self, filename: str):
        """Cargar resultados previos."""
        filepath = self.output_dir / filename
        with open(filepath, "r") as f:
            data = json.load(f)
        
        self.results = [BenchmarkResult(**r) for r in data["results"]]
    
    def print_summary(self):
        """Imprimir resumen de resultados."""
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)
        
        by_dataset: Dict[str, List[BenchmarkResult]] = {}
        for result in self.results:
            if result.dataset not in by_dataset:
                by_dataset[result.dataset] = []
            by_dataset[result.dataset].append(result)
        
        for dataset, results in by_dataset.items():
            print(f"\nDataset: {dataset} ({results[0].n_routes} routes)")
            print("-" * 70)
            print(f"{'Algorithm':<20} {'Buses':>8} {'Time(ms)':>10} {'Score':>12} {'Grade':>8}")
            print("-" * 70)
            
            for r in sorted(results, key=lambda x: x.objective_score):
                grade = r.robustness_grade or "N/A"
                print(f"{r.algorithm:<20} {r.n_buses:>8} {r.execution_time_ms:>10.0f} "
                      f"{r.objective_score:>12.2f} {grade:>8}")
            
            if len(results) > 1:
                comparison = self.compare_algorithms(results)
                print("\n  Comparisons vs Baseline:")
                for comp in comparison["comparisons"]:
                    print(f"    {comp['algorithm']}: {comp['vs_baseline']['buses']} buses, "
                          f"{comp['vs_baseline']['objective']} objective")
    
    def _default_evaluator(self, schedule: List[BusSchedule], routes: List[Route]) -> float:
        """Evaluador por defecto: minimizar buses + penalizar deadhead."""
        n_buses = len(schedule)
        total_deadhead = sum(
            item.deadhead_minutes 
            for bus in schedule 
            for item in bus.items 
            if item.deadhead_minutes > 0
        )
        # Score = buses * 1000 + deadhead (ponderado)
        return n_buses * 1000 + total_deadhead * 0.1
    
    def _calculate_avg_routes_per_bus(self, schedule: Optional[List[BusSchedule]]) -> float:
        """Calcular promedio de rutas por bus."""
        if not schedule:
            return 0.0
        total_routes = sum(len(bus.items) for bus in schedule)
        return total_routes / len(schedule)
    
    def calculate_total_km(self, schedule: Optional[List[BusSchedule]]) -> float:
        """Estimar km totales recorridos (simplificado)."""
        if not schedule:
            return 0.0
        
        # Asumir 50 km/h promedio
        AVG_SPEED_KMH = 50
        total_minutes = sum(
            item.deadhead_minutes
            for bus in schedule
            for item in bus.items
            if item.deadhead_minutes > 0
        )
        return (total_minutes / 60) * AVG_SPEED_KMH
    
    def calculate_deadhead(self, schedule: Optional[List[BusSchedule]]) -> float:
        """Calcular deadhead total en minutos."""
        if not schedule:
            return 0.0
        
        return sum(
            item.deadhead_minutes
            for bus in schedule
            for item in bus.items
            if item.deadhead_minutes > 0
        )
    
    def _determine_winner(self, a: BenchmarkResult, b: BenchmarkResult) -> str:
        """Determinar qué algoritmo es mejor basado en múltiples criterios."""
        score_a = 0
        score_b = 0
        
        # Menos buses es mejor
        if a.n_buses < b.n_buses:
            score_a += 2
        elif a.n_buses > b.n_buses:
            score_b += 2
        
        # Menos deadhead es mejor
        if a.deadhead_km < b.deadhead_km:
            score_a += 1
        elif a.deadhead_km > b.deadhead_km:
            score_b += 1
        
        # Menor score objetivo es mejor
        if a.objective_score < b.objective_score:
            score_a += 2
        elif a.objective_score > b.objective_score:
            score_b += 2
        
        # Mejor robustez
        robustness_map = {'A': 4, 'B': 3, 'C': 2, 'D': 1, 'F': 0, None: 0}
        a_robust = robustness_map.get(a.robustness_grade, 0)
        b_robust = robustness_map.get(b.robustness_grade, 0)
        
        if a_robust > b_robust:
            score_a += 1
        elif a_robust < b_robust:
            score_b += 1
        
        if score_a > score_b:
            return a.algorithm
        elif score_b > score_a:
            return b.algorithm
        else:
            return "TIE"


__all__ = ['BenchmarkSuite', 'BenchmarkResult']

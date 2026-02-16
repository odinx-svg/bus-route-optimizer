#!/usr/bin/env python3
"""
Script ejecutable para correr benchmarks comparativos.

Uso:
    python -m benchmarks.run_benchmarks
    python -m benchmarks.run_benchmarks --quick
    python -m benchmarks.run_benchmarks --dataset medium --runs 10
"""

import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from backend.models import Route
    from backend.benchmarks import BenchmarkSuite
    from backend.benchmarks.metrics import calculate_multi_objective_score
except ImportError:
    from models import Route
    from benchmarks import BenchmarkSuite
    from benchmarks.metrics import calculate_multi_objective_score


def load_dataset(name: str) -> List[Route]:
    """Cargar dataset de fixtures."""
    fixture_path = Path(__file__).parent.parent / "tests" / "fixtures" / f"routes_{name}.json"
    
    if not fixture_path.exists():
        raise FileNotFoundError(f"Dataset no encontrado: {fixture_path}")
    
    with open(fixture_path, "r") as f:
        data = json.load(f)
    
    return [Route(**r) for r in data.get("routes", [])]


def generate_synthetic_dataset(n_routes: int, seed: int = 42) -> List[Route]:
    """Generar dataset sintético para testing."""
    import random
    from datetime import time
    
    random.seed(seed)
    
    routes = []
    base_coords = [
        (42.2406, -8.7207),  # Vigo area
        (42.2450, -8.7250),
        (42.2500, -8.7300),
        (42.2350, -8.7150),
    ]
    
    schools = [
        ("Colexio Principal", 42.2500, -8.7300),
        ("Colexio Secundario", 42.2450, -8.7250),
    ]
    
    for i in range(n_routes):
        is_entry = i % 2 == 0
        school = schools[i % len(schools)]
        
        # Generar paradas aleatorias
        n_stops = random.randint(2, 5)
        stops = []
        
        for j in range(n_stops):
            base = random.choice(base_coords)
            lat = base[0] + random.uniform(-0.01, 0.01)
            lon = base[1] + random.uniform(-0.01, 0.01)
            
            stops.append({
                "name": f"Stop {i}_{j}",
                "lat": lat,
                "lon": lon,
                "order": j + 1,
                "time_from_start": j * 8,
                "passengers": random.randint(3, 12),
                "is_school": j == n_stops - 1
            })
        
        # Agregar escuela al final
        stops.append({
            "name": school[0],
            "lat": school[1],
            "lon": school[2],
            "order": n_stops + 1,
            "time_from_start": n_stops * 8 + 10,
            "passengers": 0,
            "is_school": True
        })
        
        # Horario según bloque
        block = (i % 4) + 1
        if block == 1:
            arrival = time(8 + (i % 2), (i * 10) % 60)
            departure = None
        elif block == 2:
            arrival = None
            departure = time(14, 30 + (i * 5) % 30)
        elif block == 3:
            arrival = time(16, 20 + (i * 3) % 15)
            departure = None
        else:
            arrival = None
            departure = time(18, 20 + (i * 3) % 15)
        
        route = Route(
            id=f"R{i:03d}_{'E' if is_entry else 'X'}",
            name=f"Route {i}",
            stops=stops,
            school_id=f"SCH{(i % 2) + 1}",
            school_name=school[0],
            arrival_time=arrival,
            departure_time=departure,
            capacity_needed=sum(s["passengers"] for s in stops),
            contract_id=f"UE{3600 + i}",
            type="entry" if is_entry else "exit",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    return routes


def run_comparison(
    suite: BenchmarkSuite,
    dataset_name: str,
    routes: List[Route],
    algorithms: Dict[str, callable],
    n_runs: int = 5,
    validate_robustness: bool = True
):
    """Ejecutar comparación de algoritmos en un dataset."""
    print(f"\n{'='*70}")
    print(f"Dataset: {dataset_name} ({len(routes)} routes)")
    print('='*70)
    
    results = []
    
    for algo_name, algo_func in algorithms.items():
        print(f"\n  Running {algo_name}...")
        try:
            result = suite.run_benchmark(
                algorithm=algo_func,
                algorithm_name=algo_name,
                dataset=routes,
                dataset_name=dataset_name,
                evaluator=calculate_multi_objective_score,
                n_runs=n_runs,
                validate_robustness=validate_robustness
            )
            results.append(result)
            print(f"    ✓ {result.n_buses} buses, {result.execution_time_ms:.0f}ms, "
                  f"score={result.objective_score:.1f}, grade={result.robustness_grade or 'N/A'}")
        except Exception as e:
            print(f"    ✗ Error: {e}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Run optimization benchmarks")
    parser.add_argument("--dataset", choices=["small", "medium", "large", "all"], 
                       default="all", help="Dataset to use")
    parser.add_argument("--runs", type=int, default=5, 
                       help="Number of runs per algorithm")
    parser.add_argument("--quick", action="store_true",
                       help="Quick mode: fewer runs, no robustness validation")
    parser.add_argument("--output", type=str, default=None,
                       help="Output filename for report")
    
    args = parser.parse_args()
    
    # Configurar modo
    if args.quick:
        n_runs = 2
        validate_robustness = False
        datasets_to_run = ["small"]
    else:
        n_runs = args.runs
        validate_robustness = True
        datasets_to_run = ["small", "medium", "large"] if args.dataset == "all" else [args.dataset]
    
    # Intentar cargar algoritmos
    algorithms = {}
    
    try:
        from optimizer_v6 import optimize_v6
        algorithms["greedy_v6"] = optimize_v6
    except ImportError as e:
        print(f"Warning: Could not load optimizer_v6: {e}")
    
    # Intentar cargar LNS si existe
    try:
        from optimizer_lns import optimize_v6_lns
        algorithms["lns_v6"] = optimize_v6_lns
    except ImportError:
        print("Note: optimizer_lns not available, skipping LNS comparison")
    
    # Intentar cargar multi-objectivo si existe
    try:
        from optimizer_multi import MultiObjectiveOptimizer
        mo_opt = MultiObjectiveOptimizer()
        algorithms["multi_objective"] = mo_opt.optimize
    except ImportError:
        print("Note: optimizer_multi not available")
    
    if not algorithms:
        print("Error: No algorithms available to benchmark")
        return 1
    
    print("\n" + "="*70)
    print("TUTTI OPTIMIZATION BENCHMARK SUITE")
    print("="*70)
    print(f"Algorithms: {list(algorithms.keys())}")
    print(f"Runs per algorithm: {n_runs}")
    print(f"Robustness validation: {validate_robustness}")
    
    # Inicializar suite
    suite = BenchmarkSuite()
    
    # Ejecutar benchmarks
    for dataset_name in datasets_to_run:
        try:
            routes = load_dataset(dataset_name)
        except FileNotFoundError:
            print(f"\nDataset '{dataset_name}' not found, generating synthetic...")
            n_routes = {"small": 20, "medium": 50, "large": 100}.get(dataset_name, 20)
            routes = generate_synthetic_dataset(n_routes)
            
            # Guardar para futuro
            fixture_dir = Path(__file__).parent.parent / "tests" / "fixtures"
            fixture_dir.mkdir(parents=True, exist_ok=True)
            with open(fixture_dir / f"routes_{dataset_name}.json", "w") as f:
                json.dump({"routes": [r.model_dump() for r in routes]}, f, indent=2, default=str)
            print(f"  Saved synthetic dataset to fixtures")
        
        run_comparison(
            suite=suite,
            dataset_name=dataset_name,
            routes=routes,
            algorithms=algorithms,
            n_runs=n_runs,
            validate_robustness=validate_robustness
        )
    
    # Generar reporte
    print("\n" + "="*70)
    print("GENERATING REPORT")
    print("="*70)
    
    suite.print_summary()
    
    report_path = suite.generate_report(args.output)
    print(f"\nReport saved to: {report_path}")
    
    # Guardar también en formato simple
    simple_path = suite.save_results()
    print(f"Results saved to: {simple_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

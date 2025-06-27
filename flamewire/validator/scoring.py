from typing import List, Tuple
import numpy as np

class MinerScorer:
    def __init__(self, window_size: int = 25):
        self.window_size = window_size

    def calculate_windowed_success_rate(self, last_n_checks: List[bool]) -> float:
        """Calculate weighted success rate across windows of size 5."""
        if not last_n_checks:
            return 0.0

        window = 5
        windows = []
        for i in range(len(last_n_checks), 0, -window):
            windows.append(last_n_checks[max(0, i - window) : i])

        weights = [0.333, 0.267, 0.2, 0.133, 0.067]
        rates = [sum(w) / len(w) if w else 0.0 for w in windows]

        applied_weights = weights[: len(rates)]
        total_weight = sum(applied_weights)
        weighted = sum(r * w for r, w in zip(rates, applied_weights))
        return weighted / total_weight if total_weight else 0.0

    def _metrics(self, last_n_checks: List[bool], last_n_response_times: List[float]) -> Tuple[float, float, float]:
        checks = last_n_checks[-self.window_size:] if len(last_n_checks) > self.window_size else last_n_checks
        times = last_n_response_times[-self.window_size:] if len(last_n_response_times) > self.window_size else last_n_response_times
        success_rate = self.calculate_windowed_success_rate(checks)
        if len(last_n_checks) < self.window_size:
            success_rate *= 0.8
        durations = times
        if durations:
            sorted_times = sorted(durations)
            n = len(sorted_times)
            start = int(n * 0.1)
            end = max(start + 1, int(n * 0.9))
            trimmed_durations = sorted_times[start:end]
            avg_time = np.percentile(trimmed_durations, 40) / 1000.0
        else:
            avg_time = 0.0
        speed_score = max(0.0, min(1.0, (3.0 - avg_time) / (3.0 - 0.5)))
        
        return success_rate, avg_time, speed_score

    def score(self, last_n_checks: List[bool], last_n_response_times: List[float]) -> float:
        success_rate, _, speed_score, _ = self._metrics(last_n_checks, last_n_response_times)
        score = 0.8 * success_rate + 0.2 * speed_score
        return max(score, 0.0)

    def score_with_metrics(
        self, last_n_checks: List[bool], last_n_response_times: List[float]
    ) -> Tuple[float, float, float, float]:
        """Return score along with success rate, average time and speed score."""
        success_rate, avg_time, speed_score = self._metrics(last_n_checks, last_n_response_times)
        score = self.score(last_n_checks, last_n_response_times)
        return score, success_rate, avg_time, speed_score

    @staticmethod
    def quick_score(last_n_checks: List[bool], last_n_response_times: List[float], window_size: int = 25) -> float:
        scorer = MinerScorer(window_size)
        return scorer.score(last_n_checks, last_n_response_times)
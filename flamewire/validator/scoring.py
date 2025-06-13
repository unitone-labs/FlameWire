from typing import List, Tuple

class MinerScorer:
    def __init__(self, window_size: int = 25, penalty_per_fail: float = 0.05, max_penalty: float = 0.2):
        self.window_size = window_size
        self.penalty_per_fail = penalty_per_fail
        self.max_penalty = max_penalty

    def _metrics(self, last_n_checks: List[bool], last_n_response_times: List[float]) -> Tuple[float, float, float, int]:
        checks = last_n_checks[-self.window_size:] if len(last_n_checks) > self.window_size else last_n_checks
        times = last_n_response_times[-self.window_size:] if len(last_n_response_times) > self.window_size else last_n_response_times
        success_rate = sum(checks) / len(checks) if checks else 0.0
        if len(last_n_checks) < self.window_size:
            success_rate *= 0.8
        avg_time_ms = sum(times) / len(times) if times else 0.0
        avg_time = avg_time_ms / 1000.0
        speed_score = max(0.0, min(1.0, (3.0 - avg_time) / (3.0 - 0.5)))
        fail_streak = 0
        for check in reversed(checks):
            if not check:
                fail_streak += 1
            else:
                break
        return success_rate, avg_time, speed_score, fail_streak

    def score(self, last_n_checks: List[bool], last_n_response_times: List[float]) -> float:
        success_rate, _, speed_score, fail_streak = self._metrics(last_n_checks, last_n_response_times)
        fail_streak_penalty = min(fail_streak * self.penalty_per_fail, self.max_penalty)
        score = 0.6 * success_rate + 0.4 * speed_score - fail_streak_penalty
        return max(score, 0.0)

    def score_with_metrics(
        self, last_n_checks: List[bool], last_n_response_times: List[float]
    ) -> Tuple[float, float, float, float, int]:
        """Return score along with success rate, average time, speed score and fail streak."""
        success_rate, avg_time, speed_score, fail_streak = self._metrics(last_n_checks, last_n_response_times)
        score = self.score(last_n_checks, last_n_response_times)
        return score, success_rate, avg_time, speed_score, fail_streak

    @staticmethod
    def quick_score(last_n_checks: List[bool], last_n_response_times: List[float], window_size: int = 25, penalty_per_fail: float = 0.05, max_penalty: float = 0.2) -> float:
        scorer = MinerScorer(window_size, penalty_per_fail, max_penalty)
        return scorer.score(last_n_checks, last_n_response_times) 
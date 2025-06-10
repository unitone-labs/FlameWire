from typing import List

class MinerScorer:
    def __init__(self, window_size: int = 25, penalty_per_fail: float = 0.05, max_penalty: float = 0.2):
        self.window_size = window_size
        self.penalty_per_fail = penalty_per_fail
        self.max_penalty = max_penalty

    def score(self, last_n_checks: List[bool], last_n_response_times: List[float]) -> float:
        checks = last_n_checks[-self.window_size:] if len(last_n_checks) > self.window_size else last_n_checks
        response_times = last_n_response_times[-self.window_size:] if len(last_n_response_times) > self.window_size else last_n_response_times
        if not checks:
            success_rate = 0.0
        else:
            success_rate = sum(checks) / len(checks)
        if len(last_n_checks) < self.window_size:
            success_rate *= 0.8
        if not response_times:
            speed_score = 0.0
        else:
            avg_time = sum(response_times) / len(response_times)
            speed_score = max(0.0, min(1.0, (3.0 - avg_time) / (3.0 - 0.5)))
            
        fail_streak = 0
        for check in reversed(checks):
            if not check:
                fail_streak += 1
            else:
                break
        fail_streak_penalty = min(fail_streak * self.penalty_per_fail, self.max_penalty)
        score = 0.6 * success_rate + 0.4 * speed_score - fail_streak_penalty
        return max(score, 0.0)

    @staticmethod
    def quick_score(last_n_checks: List[bool], last_n_response_times: List[float], window_size: int = 25, penalty_per_fail: float = 0.05, max_penalty: float = 0.2) -> float:
        scorer = MinerScorer(window_size, penalty_per_fail, max_penalty)
        return scorer.score(last_n_checks, last_n_response_times) 
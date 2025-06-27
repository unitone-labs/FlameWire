# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# (UnitOne Labs): Alexander
# Copyright © 2025 UnitOne Labs

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import random
import numpy as np
import bittensor as bt

from flamewire.base.validator import BaseValidatorNeuron
from flamewire.validator.verify import check_bittensor_nodes
from flamewire.api import post_node_results, get_validator_nodes
from flamewire.validator.scoring import MinerScorer

class Validator(BaseValidatorNeuron):
    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)

        bt.logging.info("load_state()")
        self.load_state()

        # Initialize wandb table for miner metrics if wandb is enabled.
        if self.wandb:
            self.miner_table = self.wandb.Table(
                columns=[
                    "tempo",
                    "round",
                    "uid",
                    "score",
                    "speed_score",
                    "avg_time",
                    "success_rate",
                ]
            )
        else:
            self.miner_table = None

    def get_shuffled_round_robin_miners(self, count=30):
        miners = [n for n in self.metagraph.neurons if n.uid != self.uid and n.validator_trust == 0]
        total_miners = len(miners)
        
        if total_miners == 0:
            return []
        
        bt.logging.info(f"miners: {len(miners)}")
        
        blocks_per_tempo = self.config.neuron.block_per_tempo
        rounds_per_tempo = (total_miners + count - 1) // count
        blocks_per_round = blocks_per_tempo // rounds_per_tempo
        
        current_tempo = self.block // blocks_per_tempo
        blocks_in_tempo = self.block % blocks_per_tempo
        round_in_tempo = blocks_in_tempo // blocks_per_round

        bt.logging.debug(
            f"Debug: miners={total_miners}, rounds_per_tempo={rounds_per_tempo}, "
            f"blocks_per_round={blocks_per_round}, current_block={self.block}, "
            f"blocks_in_tempo={blocks_in_tempo}, round_in_tempo={round_in_tempo}"
        )
        
        if round_in_tempo >= rounds_per_tempo:
            round_in_tempo = rounds_per_tempo - 1
        
        tempo_start_block = current_tempo * blocks_per_tempo
        try:
            block_hash = self.subtensor.get_block_hash(max(0, tempo_start_block - 1))
            seed = int(block_hash[-16:], 16)
        except:
            seed = current_tempo
        
        rng = random.Random(seed)
        shuffled_miners = miners.copy()
        rng.shuffle(shuffled_miners)
        
        start_idx = round_in_tempo * count
        end_idx = min(start_idx + count, total_miners)
        
        selected = shuffled_miners[start_idx:end_idx]
        
        if len(selected) < count and total_miners >= count:
            remaining = count - len(selected)
            selected += shuffled_miners[:remaining]
        
        bt.logging.info(
            f"Tempo {current_tempo}, Round {round_in_tempo + 1}/{rounds_per_tempo}: "
            f"Selected {len(selected)} miners"
        )
        
        return selected

    async def verify(self):
        bt.logging.info("verify()")

        selected_neurons = self.get_shuffled_round_robin_miners(count=30)
        current_block = self.block
        block_per_tempo = self.config.neuron.block_per_tempo
        current_tempo = current_block // block_per_tempo
        miners = [n for n in self.metagraph.neurons if n.uid != self.uid and n.validator_trust == 0]
        rounds_per_tempo = (len(miners) + 30 - 1) // 30 if miners else 1
        blocks_per_round = block_per_tempo // rounds_per_tempo
        round_in_tempo = (current_block % block_per_tempo) // blocks_per_round
        
        if not selected_neurons:
            bt.logging.info("No miners to verify in this round")
            return
        
        bt.logging.info(f"Selected {len(selected_neurons)} neurons for verification")

        results = check_bittensor_nodes(
            rpc_url=self.config.rpc_url,
            gateway_url=self.config.gateway_url,
            api_key=self.config.api_key,
            miners=selected_neurons,
            num_ref_blocks=3,
            test_runs=1
        )
        
        uids = [res.uid for res in results]

        nodes_payload = [
            {
                "uid": r.uid,
                "hotkey": r.hotkey,
                "success": r.overall_status_passed,
                "duration": r.duration,
            }
            for r in results
        ]
        
        try:
            bt.logging.info(f"POSTing {len(nodes_payload)} node results")
            post_node_results(self.config.gateway_url, self.config.api_key, nodes_payload)
            bt.logging.info("Posted node results")
        except Exception as e:
            bt.logging.error(f"Failed to post node results: {e}")
        else:
            try:
                miners = get_validator_nodes(self.config.gateway_url, self.config.api_key, uids)
                scorer = MinerScorer()
                rewards = []
                reward_uids = []
                
                for m in miners:
                    last_checks = m.get("last_n_checks", [])
                    last_times = m.get("last_n_response_times", [])
                    score, success_rate, avg_time, speed_score = scorer.score_with_metrics(last_checks, last_times)

                    bt.logging.info(
                        f"Miner {m.get('uid')}: avg_time={avg_time:.2f}s, "
                        f"success_rate={success_rate:.2f}, speed_score={speed_score:.2f}, "
                        f"score={score:.4f}"
                    )

                    if self.miner_table is not None:
                        self.miner_table.add_data(
                            current_tempo,
                            round_in_tempo,
                            m.get("uid"),
                            score,
                            speed_score,
                            avg_time,
                            success_rate,
                        )

                    rewards.append(score)
                    reward_uids.append(m.get("uid"))
                
                if self.wandb and self.miner_table is not None:
                    self.wandb.log({"Miners": self.miner_table}, step=current_block)
                    # Start a new table for the next round
                    self.miner_table = self.wandb.Table(
                        columns=[
                            "tempo",
                            "round",
                            "uid",
                            "score",
                            "speed_score",
                            "avg_time",
                            "success_rate",
                        ]
                    )

                bt.logging.info(f"Updating scores for uids={reward_uids} with rewards={rewards}")
                self.update_scores(rewards, reward_uids)
                bt.logging.info(f"New moving average scores: {self.scores}")
                
            except Exception as e:
                bt.logging.error(f"Failed to fetch or update scores: {e}")

if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
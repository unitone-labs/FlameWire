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

import bittensor as bt

from flamewire.base.validator import BaseValidatorNeuron
from flamewire.validator.verify import check_bittensor_nodes
from flamewire.api import post_node_results

class Validator(BaseValidatorNeuron):
    """
    Your validator neuron class. You should use this class to define your validator's behavior. In particular, you should replace the forward function with your own logic.

    This class inherits from the BaseValidatorNeuron class, which in turn inherits from BaseNeuron. The BaseNeuron class takes care of routine tasks such as setting up wallet, subtensor, metagraph, logging directory, parsing config, etc. You can override any of the methods in BaseNeuron if you need to customize the behavior.

    This class provides reasonable default behavior for a validator such as keeping a moving average of the scores of the miners and using them to set weights at the end of each epoch. Additionally, the scores are reset for new hotkeys at the end of each epoch.
    """

    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)

        bt.logging.info("load_state()")
        self.load_state()

    async def verify(self):
        bt.logging.info("verify()")
        bt.logging.info(f"Rpc url: {self.config.rpc_url}, api key: {self.config.api_key}")

        neurons = self.metagraph.neurons
        other_neurons = [n for n in neurons if n.uid != self.uid and n.validator_trust == 0]
        count = min(30, len(other_neurons))
        selected_neurons = random.sample(other_neurons, count)
        bt.logging.info(f"Selected {count} neurons for verification: {selected_neurons}")

        results = check_bittensor_nodes(
            rpc_url=self.config.rpc_url,
            gateway_url=self.config.gateway_url,
            api_key=self.config.api_key,
            miners=selected_neurons,
            num_ref_blocks=3,
            test_runs=1
        )
        bt.logging.info(f"Verification results: {results}")

        uids = [res.uid for res in results]
        rewards = [res.score for res in results]
        bt.logging.info(f"Updating scores for uids={uids} with rewards={rewards}")
        self.update_scores(rewards, uids)
        bt.logging.info(f"New moving average scores: {self.scores}")

        nodes_payload = [
            {
                "uid": r.uid,
                "hotkey": r.hotkey,
                "success": r.overall_status_passed,
                "duration": r.duration,
                "score": r.score,
            }
            for r in results
        ]
        try:
            bt.logging.info(f"POSTing {len(nodes_payload)} node results")
            post_node_results(self.config.gateway_url, self.config.api_key, nodes_payload)
            bt.logging.info("Posted node results")
        except Exception as e:
            bt.logging.error(f"Failed to post node results: {e}")

if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)

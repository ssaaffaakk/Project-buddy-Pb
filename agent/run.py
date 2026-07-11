"""Launch SSM-1.0 in the terminal."""

from ssm_agent import SSMAgent, start_cli

if __name__ == "__main__":
    agent = SSMAgent(verbose=True)
    start_cli(agent)

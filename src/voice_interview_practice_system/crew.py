from crewai import LLM  # type: ignore[import-not-found]
from crewai import Agent, Crew, Process, Task  # type: ignore[import-not-found]
from crewai.project import CrewBase, agent, crew, task  # type: ignore[import-not-found]


@CrewBase
class VoiceInterviewPracticeSystemCrew:
    """VoiceInterviewPracticeSystem crew"""

    @agent
    def dynamic_interview_conductor(self) -> Agent:
        return Agent(
            config=self.agents_config["dynamic_interview_conductor"],
            tools=[],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                # Llama 3.x ~7–8B Instruct via OpenRouter (larger than 3B for better quality)
                # OpenRouter model ID:
                #   meta-llama/llama-3.1-8b-instruct
                model="openrouter/meta-llama/llama-3.1-8b-instruct",
                temperature=0.7,
            ),
        )

    @agent
    def interview_performance_coach(self) -> Agent:
        return Agent(
            config=self.agents_config["interview_performance_coach"],
            tools=[],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                # Llama 3.x ~7–8B Instruct via OpenRouter (larger than 3B for better quality)
                # OpenRouter model ID:
                #   meta-llama/llama-3.1-8b-instruct
                model="openrouter/meta-llama/llama-3.1-8b-instruct",
                temperature=0.7,
            ),
        )

    @task
    def conduct_dynamic_interview_session(self) -> Task:
        return Task(
            config=self.tasks_config["conduct_dynamic_interview_session"],
            markdown=False,
        )

    @task
    def analyze_interview_performance(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_interview_performance"],
            markdown=False,
        )

    @crew
    def crew(self) -> Crew:
        """Creates the VoiceInterviewPracticeSystem crew"""
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )


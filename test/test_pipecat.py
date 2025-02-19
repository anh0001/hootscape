import asyncio
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from processor.echo_processor import EchoProcessor  # new import

# Define a simple service that prints out the frame content
async def echo_service(frame):
    print("Processed frame:", frame)
    return frame

async def main():
    # Build a simple pipeline by wrapping the echo_service in EchoProcessor
    pipeline = Pipeline([EchoProcessor(echo_service)])  # modified line
    task = PipelineTask(pipeline)
    runner = PipelineRunner()
    
    # Queue a test TextFrame
    await task.queue_frame(TextFrame("Hello, Pipecat!"))
    
    # Run the pipeline task
    await runner.run(task)

if __name__ == "__main__":
    asyncio.run(main())

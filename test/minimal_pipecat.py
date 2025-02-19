import asyncio
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

# Global list to capture processed frames
processed_frames = []

# Asynchronous echo service: it stores and returns the received frame.
async def echo_service(frame):
    processed_frames.append(frame)
    return frame

async def main():
    processed_frames.clear()
    
    # Construct the pipeline with the echo service.
    pipeline = Pipeline([echo_service])
    task = PipelineTask(pipeline)
    runner = PipelineRunner()
    
    # Create a test TextFrame.
    test_frame = TextFrame("Hello, Pipecat!")
    
    # Queue the test frame for processing.
    await task.queue_frame(test_frame)
    
    # Run the pipeline.
    await runner.run(task)
    
    # Validate the processing and print the outcome.
    if len(processed_frames) == 1 and processed_frames[0] == test_frame:
        print("Pipecat-ai test successful:")
        print("Processed frame:", processed_frames[0])
    else:
        print("Pipecat-ai test failed.")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.processors.frame_processor import FrameProcessor  # new import

# Global list to capture processed frames
processed_frames = []

# Remove the plain echo_service function.
# Instead, define a custom processor that wraps your echo service.
class EchoProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()  # Initialize FrameProcessor internals
        
    async def process_frame(self, frame, direction):
        processed_frames.append(frame)
        return frame

async def main():
    processed_frames.clear()
    
    # Use an instance of EchoProcessor instead of the raw function.
    pipeline = Pipeline([EchoProcessor()])
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

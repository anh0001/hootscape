import pytest
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

# Global list to capture processed frames for testing purposes
processed_frames = []

# Test service that appends the frame to the global list
async def test_echo_service(frame):
    processed_frames.append(frame)
    return frame

@pytest.mark.asyncio
async def test_pipeline_processing():
    processed_frames.clear()
    
    # Build pipeline using the test_echo_service directly, bypassing EchoProcessor
    pipeline = Pipeline([test_echo_service])
    task = PipelineTask(pipeline)
    runner = PipelineRunner()
    
    # Create and queue a test frame
    test_frame = TextFrame("Hello, Pipecat!")
    await task.queue_frame(test_frame)
    
    # Run the pipeline
    await runner.run(task)
    
    # Verify that the pipeline processed exactly one frame and it matches the test input
    assert len(processed_frames) == 1, "Expected one processed frame"
    assert processed_frames[0] == test_frame, "The processed frame does not match the input"

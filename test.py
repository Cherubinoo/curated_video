import boto3

# Create Polly client
polly = boto3.client("polly", region_name="ap-south-1")

text = "Hello! This is a test of Amazon Polly using Python and Boto3."

try:
    response = polly.synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId="Joanna",
        Engine="neural"
    )

    # Save audio to file
    with open("test.mp3", "wb") as file:
        file.write(response["AudioStream"].read())

    print("✅ Success!")
    print("Audio saved as: test.mp3")

except Exception as e:
    print("❌ Error:")
    print(e)
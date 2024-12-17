# Stage 1: Build the Python environment
FROM python:3.13-slim AS build

# Set working directory
WORKDIR /app

# Install dependencies required for building the virtual environment
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Create a virtual environment and install the dependencies
RUN python -m venv venv && \
    . venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Stage 2: Create the final image with only the necessary files
FROM python:3.13-slim AS final

# Set working directory
WORKDIR /app

# Copy virtual environment from the build stage
COPY --from=build /app/venv /app/venv

# Copy application files into the container
COPY . .

# Set environment variables
ENV PATH="/app/venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Set the entrypoint to run main.py and allow passing arguments
ENTRYPOINT ["python", "main.py"]

# Default command (can be overridden with `docker run` arguments)
CMD []
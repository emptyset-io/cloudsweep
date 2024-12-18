# Stage 1: Build the Python environment
FROM python:3.13-slim AS build

# Set working directory
WORKDIR /app

# Install dependencies required for building the virtual environment and locale settings
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Generate and set the locale (example: en_US.UTF-8)
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

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

# Install locales in the final stage and set locale environment variables
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    && locale-gen en_US.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

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

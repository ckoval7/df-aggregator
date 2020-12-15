# Use an official Python runtime as base image
FROM python:3.6-slim

# This must be set or container no go brrrr
ENV TERM=xterm

# Set the working directory
WORKDIR /df-aggregator

# Copy the current directory contents into container app dir
COPY . /df-aggregator

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Make directory for database storage volume
# RUN mkdir df-db

# Run app.py when the container launches
CMD python df-aggregator.py -d test.db
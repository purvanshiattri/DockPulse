pipeline {
    agent any

    options {
        // Prevent concurrent builds on the same agent workspace to avoid conflicts
        disableConcurrentBuilds()
        // Print build timestamps in the console logs for easier debugging
        timestamps()
    }

    stages {
        // STAGE 1: Pull the latest source code from the Git repository (GitHub)
        stage('1. Checkout Code') {
            steps {
                echo 'Checking out revision from source repository...'
                checkout scm
            }
        }

        // STAGE 2: Build the Docker image from our Dockerfile
        // --------------------------------------------------------------------------
        // ENVIRONMENT-AGNOSTIC BUILD PRINCIPLE:
        // We do not need Python or pip installed on the Jenkins container agent itself.
        // The Dockerfile handles copying requirements.txt and running 'pip install' 
        // inside an isolated, containerized environment during the build process.
        // This keeps the Jenkins host clean and avoids version conflicts between builds.
        // --------------------------------------------------------------------------
        stage('2. Docker Build') {
            steps {
                echo 'Building the DockPulse container image...'
                sh 'docker build -t dockpulse .'
            }
        }

        // STAGE 3: Deploy Container
        // --------------------------------------------------------------------------
        // AUTOMATIC DEPLOYMENT / CD PIPELINE:
        // 1. Stop Existing Container: Free up host port 5000 and the container name 
        //    'dockpulse-container' to avoid name collision and port allocation conflicts.
        // 2. Safe Removal: Safely deletes the old container resource layers.
        // 3. Port Mapping (-p 5000:5000): Maps host port 5000 to container port 5000,
        //    allowing external web traffic to reach the Flask application.
        // 4. Volume Mounting (-v /var/run/docker.sock): Mounts the host's Docker socket 
        //    so the Python Docker SDK inside the container can track real container metrics on the host.
        // --------------------------------------------------------------------------
        stage('3. Deploy Container') {
            steps {
                echo 'Stopping and cleaning up old DockPulse deployments...'
                sh 'docker stop dockpulse-container || true'
                sh 'docker rm dockpulse-container || true'
                
                echo 'Deploying fresh DockPulse container instance...'
                sh 'docker run -d -p 5000:5000 --name dockpulse-container -v /var/run/docker.sock:/var/run/docker.sock dockpulse'
            }
        }
    }

    post {
        success {
            echo '========================================================================'
            echo '  CI/CD PIPELINE EXECUTION SUCCEEDED: IMAGE BUILT & CONTAINER DEPLOYED  '
            echo '========================================================================'
        }
        failure {
            echo '========================================================================'
            echo '  CI/CD PIPELINE EXECUTION FAILED: CHECK CONSOLE OUTPUT FOR FAILURE LOG '
            echo '========================================================================'
        }
    }
}

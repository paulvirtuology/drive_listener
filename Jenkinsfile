pipeline {
    agent any

    environment {
        // Specify any environment variables you might need
        GOOGLE_APPLICATION_CREDENTIALS = credentials('google-service-account') // Reference to Jenkins stored credentials
    }

    stages {
        stage('Setup') {
            steps {
                script {
                    // Clean up old credentials if needed
                    sh 'rm -f token.pickle'
                }
                echo 'Setting up the environment...'
                // Install necessary packages and dependencies
                sh 'pip install --upgrade google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client'
            }
        }

        stage('Run Monitoring Script') {
            steps {
                echo 'Running Google Drive monitoring script...'
                // Run the Python script
                sh 'python main.py'
            }
        }
    }

    post {
        success {
            echo 'Job succeeded!'
        }
        failure {
            echo 'Job failed!'
        }
    }
}

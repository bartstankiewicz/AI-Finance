from bottle import Bottle, response
from monitor import Monitor
from publisher import MonitorPublisher


class MonitoringServiceApi(Bottle):
    def __init__(self, monitor: Monitor, publisher: MonitorPublisher):
        super().__init__()
        self.monitor = monitor
        self.publisher = publisher
        self.route('/health', method='GET', callback=self.health)
        self.route('/status', method='GET', callback=self.service_status)
        self.route('/stream', method='GET', callback=self.stream)

    def health(self):
        """Health check requested"""
        health_status = {
            "service": "monitoring-service",
            "status": "UP"
        }
        return health_status

    def service_status(self):
        """Get the current status of the monitored services"""
        return self.monitor.status

    def stream(self):
        """Stream events from the monitoring service"""
        response.content_type = "text/event-stream"
        response.set_header("Cache-Control", "no-cache")
        return self.publisher.stream_events()

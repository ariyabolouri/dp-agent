from collections import defaultdict, Counter


class Service:
    def __init__(self, name, connector=None, state_processor_method=None,
                 batch_size=1, tags=None, names_previous_services=None,
                 workflow_formatter=None, connector_callable=None):
        self.name = name
        self.batch_size = batch_size
        self.state_processor_method = state_processor_method
        self.names_previous_services = names_previous_services or set()
        self.tags = tags or []
        self.workflow_formatter = workflow_formatter
        if not (connector or connector_callable):
            raise ValueError('Either connector or connector_callable should be provided')
        self.connector = connector
        self._connector_callable = connector_callable
        self.previous_services = set()
        self.next_services = set()

    def is_selector(self):
        return 'selector' in self.tags

    def is_responder(self):
        return 'responder' in self.tags

    def apply_workflow_formatter(self, workflow_record):
        if not self.workflow_formatter:
            return workflow_record
        return self.workflow_formatter(workflow_record)

    @property
    def connector_callable(self):
        if self._connector_callable:
            return self._connector_callable
        else:
            return self.connector.send


class Pipeline:
    def __init__(self, services):
        wrong_names = [k for k, v in Counter([i.name for i in services]).items() if v != 1]
        if wrong_names:
            raise ValueError(f'there are some duplicate service names presented {wrong_names}')

        self.services = {i.name: i for i in services}
        wrong_links = self.process_service_names()
        if wrong_links:
            print('wrong links in config were detected: ', dict(wrong_links))

    def get_service_by_name(self, service_name):
        if not service_name:
            return None

        service = self.services.get(service_name, None)
        if not service:
            raise ValueError(f'service {service_name} does not exist')
        return service

    def process_service_names(self):
        wrong_names = defaultdict(list)
        for service in self.services.values():
            for name_prev_service in service.names_previous_services:
                if name_prev_service not in self.services:
                    wrong_names[service.name].append(name_prev_service)
                    continue
                service.previous_services.add(self.services[name_prev_service])
                self.services[name_prev_service].next_services.add(service)
        return wrong_names  # wrong names means that some service_names, used in previous services don't exist

    def get_next_services(self, done=None, waiting=None):
        if not done:
            done = set()
        if not waiting:
            waiting = set()
        removed_names = waiting | done
        for name, service in self.services.items():
            if not {i.name for i in service.previous_services} <= done:
                removed_names.add(name)

        return [service for name, service in self.services.items() if name not in removed_names]

    def get_endpoint_services(self):
        return [s for s in self.services.values() if not s.next_services and 'responder' not in s.tags]

    def add_responder_service(self, service):
        if 'responder' not in service.tags:
            raise ValueError('service should be a responder')
        endpoints = self.get_endpoint_services()
        service.previous_services = set(endpoints)
        service.previous_service_names = {s.name for s in endpoints}
        self.services[service.name] = service

        for s in endpoints:
            self.services[s.name].next_services.add(service)


def simple_workflow_formatter(workflow_record):
    return workflow_record['dialog'].to_dict()

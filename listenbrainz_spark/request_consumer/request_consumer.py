# listenbrainz-labs
#
# Copyright (C) 2019 Param Singh <iliekcomputers@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import threading

import pika
import json
import time
import logging

import listenbrainz_spark
import listenbrainz_spark.query_map
from listenbrainz_spark import config
from listenbrainz_spark.request_consumer.result_publisher import invoke_query
from listenbrainz_spark.utils import init_rabbitmq

from py4j.protocol import Py4JJavaError


rc = None
logger = logging.getLogger(__name__)


class RequestConsumer:

    def get_query(self, request):
        try:
            query = request['query']
            params = request.get('params', {})
        except Exception:
            logger.error('Bad query sent to spark request consumer: %s', json.dumps(request), exc_info=True)
            return None

        logger.info('Query: %s', query)
        logger.info('Params: %s', str(params))

        try:
            query_handler = listenbrainz_spark.query_map.get_query_handler(query)
        except KeyError:
            logger.error("Bad query sent to spark request consumer: %s", query, exc_info=True)
            return None
        except Exception:
            logger.error("Error while mapping query to function:", exc_info=True)
            return None

        return query_handler, params

    def callback(self, channel, method, properties, body):
        logger.info("Callback entered")
        request = json.loads(body.decode('utf-8'))
        logger.info('Received a request!')

        query = self.get_query(request)
        threading.Thread(
            target=invoke_query,
            args=(
                self.rabbitmq,
                self.request_channel,
                method.delivery_tag,
                *query,
                self.publish_messages
            )
        ).start()
        logger.info("Callback exited")

    def publish_messages(self, messages):
        for message in messages:
            try:
                self.result_channel.basic_publish(
                    exchange=config.SPARK_RESULT_EXCHANGE,
                    routing_key='',
                    body=message,
                    properties=pika.BasicProperties(delivery_mode=2, ),
                )
                break
                # we do not catch ConnectionClosed exception here because when
                # a connection closes so do all of the channels on it. so if the
                # connection is closed, we have lost the request channel. hence,
                # we'll be unable to ack the request later and receive it again
                # for processing anyways.
            except pika.exceptions.ChannelClosed:
                logger.error('RabbitMQ Connection error while publishing results:', exc_info=True)
                time.sleep(1)
                self.init_result_channel()

    def connect_to_rabbitmq(self):
        self.rabbitmq = init_rabbitmq(
            username=config.RABBITMQ_USERNAME,
            password=config.RABBITMQ_PASSWORD,
            host=config.RABBITMQ_HOST,
            port=config.RABBITMQ_PORT,
            vhost=config.RABBITMQ_VHOST,
            connection_name="listenbrainz-spark-request-consumer",
        )

    def init_request_channel(self):
        self.request_channel = self.rabbitmq.channel()
        self.request_channel.exchange_declare(exchange=config.SPARK_REQUEST_EXCHANGE, exchange_type='fanout')
        self.request_channel.queue_declare(config.SPARK_REQUEST_QUEUE, durable=True)
        self.request_channel.queue_bind(
            exchange=config.SPARK_REQUEST_EXCHANGE,
            queue=config.SPARK_REQUEST_QUEUE
        )

        # By default, rabbitmq tries to send as many messages as possible at a time
        # All of these are marked as unacked. We don't get to the later messages
        # until the current spark request is complete so we inevitably hit a consumer
        # ack timeout on those. To fix this request rabbitmq to send only one message
        # at a time. The next message isn't sent until the current one has been ack'ed.
        self.request_channel.basic_qos(prefetch_count=1)

        # basic_consume should be called after basic_qos otherwise basic_qos doesn't eork
        self.request_channel.basic_consume(queue=config.SPARK_REQUEST_QUEUE, on_message_callback=self.callback)

    def init_result_channel(self):
        self.result_channel = self.rabbitmq.channel()
        self.result_channel.exchange_declare(
            exchange=config.SPARK_RESULT_EXCHANGE,
            exchange_type='fanout'
        )

    def run(self):
        while True:
            try:
                self.connect_to_rabbitmq()
                self.init_request_channel()
                self.init_request_channel()
                logger.info('Request consumer started!')

                try:
                    self.request_channel.start_consuming()
                except pika.exceptions.ConnectionClosed as e:
                    logger.error('connection to rabbitmq closed: %s', str(e), exc_info=True)
                    self.rabbitmq.close()
                    continue
                self.rabbitmq.close()
            except Py4JJavaError as e:
                logger.critical("Critical: JAVA error in spark-request consumer: %s, message: %s",
                                            str(e), str(e.java_exception), exc_info=True)
                time.sleep(2)
                self.publisher.shutdown()
            except Exception as e:
                logger.critical("Error in spark-request-consumer: %s", str(e), exc_info=True)
                time.sleep(2)
                self.publisher.shutdown()

    def ping(self):
        """ Sends a heartbeat to rabbitmq to avoid closing the connection during long processes """
        self.rabbitmq.process_data_events(0)


def main(app_name):
    listenbrainz_spark.init_spark_session(app_name)
    global rc
    rc = RequestConsumer()
    rc.run()


if __name__ == '__main__':
    main('spark-writer')

import asyncio
from unittest import mock
import contexts
import asynqp


class ProtocolContext:
    def establish_the_connection(self):
        self.transport = mock.Mock(spec=asyncio.Transport)
        self.connection = mock.Mock(spec=asynqp.Connection)
        self.protocol = asynqp.AMQP(self.connection)
        self.protocol.connection_made(self.transport)



class WhenAWholeFrameArrives(ProtocolContext):
    def establish_the_frame(self):
        self.raw = b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE'
        method = asynqp.methods.ConnectionOpenOK()
        self.expected_frame = asynqp.Frame(asynqp.FrameType.method, 0, method)

    def because_the_whole_frame_arrives(self):
        self.protocol.data_received(self.raw)

    def it_should_dispatch_the_method(self):
        self.connection.handle_ConnectionOpenOK.assert_called_once_with(self.expected_frame)


class WhenAFrameDoesNotEndInFrameEnd(ProtocolContext):
    def establish_the_bad_frame(self):
        self.raw = b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCD'

    def because_the_bad_frame_arrives(self):
        self.exception = contexts.catch(self.protocol.data_received, self.raw)

    def it_should_raise_an_exception(self):
        assert isinstance(self.exception, asynqp.AMQPError)


class WhenHalfAFrameArrives(ProtocolContext):
    @classmethod
    def examples_of_incomplete_frames(cls):
        yield b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00'  # cut off half way through the payload
        yield b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00'  # cut off right before the frame end byte
        yield b'\x01\x00'  # cut off before the end of the header

    def because_the_whole_frame_arrives(self, raw):
        self.protocol.data_received(raw)

    def it_should_notdispatch_the_method(self):
        assert not self.connection.handle_ConnectionOpenOK.called


class WhenAFrameArrivesInTwoParts(ProtocolContext):
    @classmethod
    def examples_of_broken_up_frames(cls):
        yield  b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A', b'\x00\x29\x00\xCE'  # cut off half way through the payload
        yield  b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00', b'\xCE'  # cut off right before the frame end byte
        yield  b'\x01\x00', b'\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE'  # cut off before the end of the header
    def establish_the_frame(self):
        method = asynqp.methods.ConnectionOpenOK()
        self.expected_frame = asynqp.Frame(asynqp.FrameType.method, 0, method)

    def because_the_whole_frame_eventually_arrives(self, raw1, raw2):
        self.protocol.data_received(raw1)
        self.protocol.data_received(raw2)

    def it_should_dispatch_the_method(self):
        self.connection.handle_ConnectionOpenOK.assert_called_once_with(self.expected_frame)


class WhenMoreThanAWholeFrameArrives(ProtocolContext):
    def establish_the_frame(self):
        self.raw = b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE\x01\x00\x00\x00\x00\x00\x05\x00\x0A'
        method = asynqp.methods.ConnectionOpenOK()
        self.expected_frame = asynqp.Frame(asynqp.FrameType.method, 0, method)

    def because_more_than_a_whole_frame_arrives(self):
        self.protocol.data_received(self.raw)

    def it_should_dispatch_the_method_once(self):
        self.connection.handle_ConnectionOpenOK.assert_called_once_with(self.expected_frame)


class WhenTwoFramesArrive(ProtocolContext):
    def establish_the_frame(self):
        self.raw = b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE'
        method = asynqp.methods.ConnectionOpenOK()
        self.expected_frame = asynqp.Frame(asynqp.FrameType.method, 0, method)

    def because_more_than_a_whole_frame_arrives(self):
        self.protocol.data_received(self.raw)

    def it_should_dispatch_the_method_twice(self):
        self.connection.handle_ConnectionOpenOK.assert_has_calls([mock.call(self.expected_frame), mock.call(self.expected_frame)])


class WhenTwoFramesArrivePiecemeal(ProtocolContext):
    @classmethod
    def examples_of_broken_up_frames(cls):
        yield b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE', b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE'
        yield b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00', b'\x29\x00\xCE'
        yield b'\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE\x01\x00', b'\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE'
        yield b'\x01', b'\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE\x01\x00\x00\x00\x00\x00\x05\x00\x0A\x00\x29\x00\xCE'
        yield b'\x01', b'\x00\x00\x00\x00\x00\x05\x00', b'\x0A\x00\x29\x00', b'\xCE\x01\x00\x00\x00\x00\x00\x05\x00', b'\x0A\x00\x29\x00\xCE', b''

    def establish_what_we_expected(self):
        method = asynqp.methods.ConnectionOpenOK()
        self.expected_frame = asynqp.Frame(asynqp.FrameType.method, 0, method)

    def because_two_frames_arrive_in_bits(self, fragments):
        for fragment in fragments:
            self.protocol.data_received(fragment)

    def it_should_dispatch_the_method_twice(self):
        self.connection.handle_ConnectionOpenOK.assert_has_calls([mock.call(self.expected_frame), mock.call(self.expected_frame)])

"""
VideoXBlock mixins test cases.
"""

import json
from collections import Iterable, OrderedDict

from django.test import RequestFactory
from mock import patch, Mock, MagicMock, PropertyMock
from webob import Response
from xblock.exceptions import NoSuchServiceError

from video_xblock.constants import DEFAULT_LANG, TPMApiLanguage
from video_xblock.tests.unit.base import VideoXBlockTestBase
from video_xblock.tests.unit.mocks.base import ResponseStub
from video_xblock.tests.unit.test_video_xblock_handlers import arrange_request_mock
from video_xblock.utils import loader, Transcript
from video_xblock.video_xblock import VideoXBlock


class ContentStoreMixinTest(VideoXBlockTestBase):
    """Test ContentStoreMixin"""

    @patch('video_xblock.mixins.import_from')
    def test_contentstore_no_service(self, import_mock):
        import_mock.return_value = 'contentstore_test'

        self.assertEqual(self.xblock.contentstore, 'contentstore_test')
        import_mock.assert_called_once_with('xmodule.contentstore.django', 'contentstore')

    @patch('video_xblock.mixins.import_from')
    def test_static_content_no_service(self, import_mock):
        import_mock.return_value = 'StaticContent_test'

        self.assertEqual(self.xblock.static_content, 'StaticContent_test')
        import_mock.assert_called_once_with('xmodule.contentstore.content', 'StaticContent')

    def test_contentstore(self):
        with patch.object(self.xblock, 'runtime') as runtime_mock:
            service_mock = runtime_mock.service
            type(service_mock.return_value).contentstore = cs_mock = PropertyMock(
                return_value='contentstore_test'
            )

            self.assertEqual(self.xblock.contentstore, 'contentstore_test')
            service_mock.assert_called_once_with(self.xblock, 'contentstore')
            cs_mock.assert_called_once()

    def test_static_content(self):
        with patch.object(self.xblock, 'runtime') as runtime_mock:
            service_mock = runtime_mock.service
            type(service_mock.return_value).StaticContent = sc_mock = PropertyMock(
                return_value='StaticContent_test'
            )

            self.assertEqual(self.xblock.static_content, 'StaticContent_test')
            service_mock.assert_called_once_with(self.xblock, 'contentstore')
            sc_mock.assert_called_once()


class LocationMixinTests(VideoXBlockTestBase):
    """Test LocationMixin"""

    def test_xblock_doesnt_have_location_by_default(self):
        self.assertFalse(hasattr(self.xblock, 'location'))

    def test_fallback_block_id(self):
        self.assertEqual(self.xblock.block_id, 'block_id')

    def test_fallback_course_key(self):
        self.assertEqual(self.xblock.course_key, 'course_key')

    def test_fallback_usage_id(self):
        self.assertEqual(self.xblock.usage_id, 'usage_id')

    def test_block_id(self):
        self.xblock.location = Mock()
        type(self.xblock.location).block_id = block_mock = PropertyMock(
            return_value='test_block_id'
        )

        self.assertEqual(self.xblock.block_id, 'test_block_id')
        block_mock.assert_called_once()

    def test_course_key(self):
        self.xblock.location = Mock()

        type(self.xblock.location).course_key = course_key_mock = PropertyMock(
            return_value='test_course_key'
        )

        self.assertEqual(self.xblock.course_key, 'test_course_key')
        course_key_mock.assert_called_once()

    def test_usage_id(self):
        self.xblock.location = Mock()
        self.xblock.location.to_deprecated_string = str_mock = Mock(
            return_value='test_str'
        )

        self.assertEqual(self.xblock.usage_id, 'test_str')
        str_mock.assert_called_once()


class PlaybackStateMixinTests(VideoXBlockTestBase):
    """Test PlaybackStateMixin"""

    def test_fallback_course_default_language(self):
        with patch.object(self.xblock, 'runtime') as runtime_mock:
            runtime_mock.service = service_mock = Mock(side_effect=NoSuchServiceError)

            self.assertEqual(self.xblock.course_default_language, DEFAULT_LANG)
            service_mock.assert_called_once()

    def test_course_default_language(self):
        with patch.object(self.xblock, 'runtime') as runtime_mock:
            service_mock = runtime_mock.service
            lang_mock = type(service_mock.return_value.get_course.return_value).language = PropertyMock(
                return_value='test_lang'
            )
            lang_mock.return_value = 'test_lang'
            self.xblock.course_id = course_id_mock = PropertyMock()

            self.assertEqual(self.xblock.course_default_language, 'test_lang')
            service_mock.assert_called_once_with(self.xblock, 'modulestore')
            lang_mock.assert_called_once()
            course_id_mock.assert_not_called()

    def test_player_state(self):
        """
        Test player state property.
        """
        self.xblock.course_id = 'test:course:id'
        self.xblock.runtime.modulestore = Mock(get_course=Mock)
        self.assertDictEqual(
            self.xblock.player_state,
            {
                'currentTime': self.xblock.current_time,
                'muted': self.xblock.muted,
                'playbackRate': self.xblock.playback_rate,
                'volume': self.xblock.volume,
                'transcripts': [],
                'transcriptsEnabled': self.xblock.transcripts_enabled,
                'captionsEnabled': self.xblock.captions_enabled,
                'captionsLanguage': 'en',
                'transcriptsObject': {}
            }
        )

    def test_save_player_state(self):
        """
        Test player state saving.
        """
        self.xblock.course_id = 'test:course:id'
        self.xblock.runtime.modulestore = Mock(get_course=Mock)
        data = {
            'currentTime': 5,
            'muted': True,
            'playbackRate': 2,
            'volume': 0.5,
            'transcripts': [],
            'transcriptsEnabled': True,
            'captionsEnabled': True,
            'captionsLanguage': 'ru',
            'transcriptsObject': {}
        }
        factory = RequestFactory()
        request = factory.post('', json.dumps(data), content_type='application/json')

        response = self.xblock.save_player_state(request)

        self.assertEqual('{"success": true}', response.body)  # pylint: disable=no-member
        self.assertDictEqual(self.xblock.player_state, {
            'currentTime': data['currentTime'],
            'muted': data['muted'],
            'playbackRate': data['playbackRate'],
            'volume': data['volume'],
            'transcripts': data['transcripts'],
            'transcriptsEnabled': data['transcriptsEnabled'],
            'captionsEnabled': data['captionsEnabled'],
            'captionsLanguage': data['captionsLanguage'],
            'transcriptsObject': {}
        })


class SettingsMixinTests(VideoXBlockTestBase):
    """
    Test SettingsMixin
    """

    def test_block_settings_key_is_correct(self):
        self.assertEqual(self.xblock.block_settings_key, 'video_xblock')

    @patch('video_xblock.mixins.import_from')
    def test_settings_property_with_runtime_service(self, import_from_mock):
        with patch.object(self.xblock, 'runtime') as runtime_mock:
            # Arrange
            service_mock = runtime_mock.service
            settings_bucket_mock = service_mock.return_value.get_settings_bucket
            settings_bucket_mock.return_value = {'foo': 'bar'}

            # Act
            settings = self.xblock.settings

            # Assert
            self.assertEqual(settings, {'foo': 'bar'})
            service_mock.assert_called_once_with(self.xblock, 'settings')
            settings_bucket_mock.assert_called_once_with(self.xblock)
            import_from_mock.assert_not_called()

    @patch('video_xblock.mixins.import_from')
    def test_settings_property_without_runtime_service(self, import_from_mock):
        with patch.object(self.xblock, 'runtime') as runtime_mock:
            # Arrange
            service_mock = runtime_mock.service
            service_mock.return_value = None
            get_settings_mock = import_from_mock.return_value.XBLOCK_SETTINGS.get
            get_settings_mock.return_value = {'foo': 'bar'}

            # Act
            settings = self.xblock.settings

            # Assert
            self.assertEqual(settings, {'foo': 'bar'})
            import_from_mock.assert_called_once_with('django.conf', 'settings')
            get_settings_mock.assert_called_once_with(
                self.xblock.block_settings_key, {}
            )

    @patch.object(VideoXBlock, 'settings', new_callable=PropertyMock)
    def test_populate_default_values(self, settings_mock):
        # Arrange
        settings_mock.return_value = {'foo': 'another bar', 'spam': 'eggs'}
        xblock_fields_dict = {'foo': 'bar'}

        # Act
        populated_xblock_fields = self.xblock.populate_default_values(xblock_fields_dict)

        # Assert
        self.assertEqual(populated_xblock_fields, {'foo': 'bar', 'spam': 'eggs'})


class TranscriptsMixinTests(VideoXBlockTestBase):  # pylint: disable=test-inherits-tests
    """Test TranscriptsMixin"""

    @patch('video_xblock.mixins.WebVTTWriter.write')
    @patch('video_xblock.mixins.detect_format')
    def test_convert_caps_to_vtt(self, detect_format_mock, vtt_writer_mock):
        detect_format_mock.return_value.return_value.read = read_mock = Mock()
        read_mock.return_value = 'non vtt transcript'
        vtt_writer_mock.return_value = 'vtt transcript'

        self.assertEqual(self.xblock.convert_caps_to_vtt('test caps'), 'vtt transcript')
        vtt_writer_mock.assert_called_once_with('non vtt transcript')

    @patch('video_xblock.mixins.WebVTTWriter.write')
    @patch('video_xblock.mixins.detect_format')
    def test_convert_caps_to_vtt_fallback(self, detect_format_mock, vtt_writer_mock):
        detect_format_mock.return_value = None

        self.assertEqual(self.xblock.convert_caps_to_vtt('test caps'), u'')
        vtt_writer_mock.assert_not_called()
        detect_format_mock.assert_called_once_with('test caps')

    @patch.object(VideoXBlock, 'static_content')
    @patch.object(VideoXBlock, 'contentstore')
    @patch.object(VideoXBlock, 'course_key', new_callable=PropertyMock)
    def test_create_transcript_file(self, course_key, contentstore_mock, static_content_mock):
        # Arrange
        trans_srt_stub = 'test srt transcript'
        reference_name_stub = 'test transcripts'
        static_content_mock.compute_location = Mock(return_value='test-location.vtt')
        save_mock = contentstore_mock.return_value.save

        # Act
        file_name, external_url = self.xblock.create_transcript_file(
            trans_str=trans_srt_stub, reference_name=reference_name_stub
        )

        # Assert
        static_content_mock.assert_called_with(
            'test-location.vtt', 'test_transcripts.vtt', 'application/json', u'test srt transcript'
        )
        save_mock.assert_called_once_with(static_content_mock.return_value)
        course_key.assert_called_once_with()

        self.assertEqual(file_name, 'test_transcripts.vtt')
        self.assertEqual(external_url, '/test-location.vtt')

    @patch.object(VideoXBlock, 'get_file_name_from_path')
    @patch('video_xblock.mixins.requests.get')
    def test_download_transcript_handler_response_object(self, get_mock, get_filename_mock):
        # Arrange
        get_filename_mock.return_value = 'transcript.vtt'
        get_mock.return_value.text = 'vtt transcripts'
        request_mock = MagicMock()
        request_mock.host_url = 'test.host'
        request_mock.query_string = '/test-query-string'

        # Act
        vtt_response = self.xblock.download_transcript(request_mock, 'unused suffix')

        # Assert
        self.assertIsInstance(vtt_response, Response)
        self.assertEqual(vtt_response.text, 'vtt transcripts')
        self.assertEqual(vtt_response.headerlist, [
            ('Content-Type', 'text/plain'),
            ('Content-Disposition', 'attachment; filename={}'.format('transcript.vtt'))
        ])
        get_mock.assert_called_once_with('test.host/test-query-string')

    @patch.object(VideoXBlock, 'captions_language', new_callable=PropertyMock)
    @patch.object(VideoXBlock, 'transcripts', new_callable=PropertyMock)
    def test_get_transcript_download_link(self, trans_mock, lang_mock):
        lang_mock.return_value = 'en'
        trans_mock.return_value = '[{"lang": "en", "url": "test_transcript.vtt"}]'

        self.assertEqual(self.xblock.get_transcript_download_link(), 'test_transcript.vtt')

    @patch.object(VideoXBlock, 'transcripts', new_callable=PropertyMock)
    def test_get_transcript_download_link_fallback(self, trans_mock):
        trans_mock.return_value = ''

        self.assertEqual(self.xblock.get_transcript_download_link(), '')

    def test_route_transcripts(self):
        # Arrange
        transcripts = [{"url": "test-trans.srt"}]
        with patch.object(self.xblock, 'runtime') as runtime_mock, \
                patch.object(self.xblock, 'get_enabled_transcripts') as get_enabled_transcripts_mock:
            handler_url_mock = runtime_mock.handler_url
            handler_url_mock.return_value = 'test-trans.vtt'
            get_enabled_transcripts_mock.return_value = transcripts
            self.xblock.threeplaymedia_streaming = False

            # Act
            transcripts_routes = self.xblock.route_transcripts()

            # Assert
            self.assertIsInstance(transcripts_routes, Iterable)
            self.assertEqual(next(transcripts_routes), {'url': 'test-trans.vtt'})
            handler_url_mock.assert_called_once_with(
                self.xblock, 'srt_to_vtt', query='test-trans.srt'
            )

    @patch('video_xblock.mixins.requests', new_callable=MagicMock)
    @patch.object(VideoXBlock, 'convert_caps_to_vtt')
    def test_srt_to_vtt(self, convert_caps_to_vtt_mock, requests_mock):
        # Arrange
        request_mock = MagicMock()
        convert_caps_to_vtt_mock.return_value = 'vtt transcripts'
        requests_mock.get.return_value.text = text_mock = PropertyMock()
        text_mock.return_value = 'vtt transcripts'

        # Act
        vtt_response = self.xblock.srt_to_vtt(request_mock, 'unused suffix')

        # Assert
        self.assertIsInstance(vtt_response, Response)
        self.assertEqual(vtt_response.text, 'vtt transcripts')
        convert_caps_to_vtt_mock.assert_called_once_with(text_mock)

    def test_fetch_available_3pm_transcripts_with_errors(self):
        # Arrange:
        test_results = {'errors': ['test_errors']}
        with patch.object(self.xblock, 'get_available_3pm_transcripts') as threepm_transcripts_mock, \
                patch.object(self.xblock, 'threeplaymedia_file_id') as file_id_mock, \
                patch.object(self.xblock, 'threeplaymedia_apikey') as apikey_mock:

            threepm_transcripts_mock.return_value = test_results
            # Act:
            transcripts_gen = self.xblock.fetch_available_3pm_transcripts()
            transcripts = list(transcripts_gen)
            # Assert:
            self.assertEqual(transcripts, [])
            self.assertRaises(StopIteration, transcripts_gen.next)
            threepm_transcripts_mock.assert_called_once_with(file_id_mock, apikey_mock)

    def test_fetch_available_3pm_transcripts_success(self):
        # Arrange:
        test_transcript_data = [{'id': 'test_id', 'language_id': '2'}]
        test_args = ['id', 'label', 'lang', 'lang_id', 'content', 'format', 'video_id', 'source', 'url']
        with patch.object(self.xblock, 'get_available_3pm_transcripts') as threepm_transcripts_mock, \
                patch.object(self.xblock, 'fetch_3pm_translation') as fetch_3pm_translation_mock, \
                patch.object(self.xblock, 'threeplaymedia_file_id') as file_id_mock, \
                patch.object(self.xblock, 'threeplaymedia_apikey') as apikey_mock:

            threepm_transcripts_mock.return_value = test_transcript_data
            fetch_3pm_translation_mock.return_value = Transcript(*test_args)
            # Act:
            transcripts_gen = self.xblock.fetch_available_3pm_transcripts()
            transcripts = list(transcripts_gen)
            # Assert:
            self.assertIsInstance(transcripts[0], OrderedDict)
            self.assertSequenceEqual(test_args, transcripts[0].keys())
            threepm_transcripts_mock.assert_called_once_with(file_id_mock, apikey_mock)
            fetch_3pm_translation_mock.assert_called_once_with(test_transcript_data[0])

    @patch('video_xblock.mixins.requests.get')
    def test_get_available_3pm_transcripts(self, requests_get_mock):
        # Arrange:
        test_json = '{"test":"json_string"}'
        requests_get_mock.return_value = ResponseStub(
            body=test_json,
            ok=True
        )
        file_id = 'test_file_id'
        api_key = 'test_api_key'
        test_api_url = 'https://static.3playmedia.com/files/test_file_id/transcripts?apikey=test_api_key'
        # Act:
        results = self.xblock.get_available_3pm_transcripts(file_id, api_key)
        # Assert:
        self.assertTrue(requests_get_mock.ok)
        self.assertTrue(requests_get_mock.json.assert_called)
        self.assertEqual(results, test_json)
        requests_get_mock.assert_called_once_with(test_api_url)

    @patch.object(VideoXBlock, 'get_player')
    @patch('video_xblock.mixins.requests.get')
    def test_fetch_3pm_translation(self, requests_get_mock, player_mock):
        # Arrange:
        test_lang_id = '1'
        test_transcript_text = 'test_transcript_text'
        test_format = 51
        test_transcript_id = 'test_id'
        test_video_id = 'test_video_id'
        test_source = '3play-media'
        file_id = 'test_file_id'
        api_key = 'test_api_key'

        test_transcript_data = {'id': test_transcript_id, 'language_id': test_lang_id}
        test_lang_code = TPMApiLanguage(test_lang_id)
        test_api_url = 'https://static.3playmedia.com/files/test_file_id/transcripts/test_id?' \
                       'apikey=test_api_key&format_id=51'

        requests_get_mock.return_value = ResponseStub(body=test_transcript_text)
        media_id_mock = player_mock.return_value.media_id
        media_id_mock.return_value = test_video_id
        self.xblock.threeplaymedia_file_id = file_id
        self.xblock.threeplaymedia_apikey = api_key

        test_args = [
            test_transcript_id,
            test_lang_code.name,
            test_lang_code.iso_639_1_code,
            test_lang_id,
            test_transcript_text,
            test_format,
            test_video_id,
            test_source,
            test_api_url
        ]

        # Act:
        transcript = self.xblock.fetch_3pm_translation(test_transcript_data)
        # Assert:
        self.assertEqual(transcript, Transcript(*test_args))

    @patch.object(VideoXBlock, 'get_translations_from_3playmedia')
    def test_get_transcripts_3playmedia_api_handler_success(self, threeplaymedia_fetcher_mock):
        # Arrange:
        request_body = '{"api_key": "test_api_key","file_id": "test_file_id"}'
        request_mock = arrange_request_mock(request_body)

        test_status = "not_error"
        test_transcripts = 'test_transcripts'
        threeplaymedia_fetcher_mock.return_value = test_status, test_transcripts

        # Act:
        response = self.xblock.get_transcripts_3playmedia_api_handler(request_mock)

        # Assert:
        self.assertEqual(
            '{"transcripts": "test_transcripts", "success_message": "Successfully fetched transcripts '
            'from 3playMedia. Please check transcripts list above."}',
            response.body  # pylint: disable=no-member
        )

    @patch.object(VideoXBlock, 'get_translations_from_3playmedia')
    def test_get_transcripts_3playmedia_api_handler_failure(self, threeplaymedia_fetcher_mock):
        # Arrange:
        request_body = '{"api_key": "test_api_key","file_id": "test_file_id"}'
        request_mock = arrange_request_mock(request_body)

        test_status = "error"
        test_transcripts = 'test_transcripts'
        threeplaymedia_fetcher_mock.return_value = test_status, test_transcripts

        # Act:
        response = self.xblock.get_transcripts_3playmedia_api_handler(request_mock)

        # Assert:
        self.assertEqual('"test_transcripts"', response.body)  # pylint: disable=no-member


class WorkbenchMixinTest(VideoXBlockTestBase):
    """Test WorkbenchMixin"""

    @patch.object(loader, 'load_scenarios_from_path')
    def test_workbench_scenarios(self, loader_mock):
        loader_mock.return_value = [('Scenario', '<xml/>')]

        self.assertEqual(self.xblock.workbench_scenarios(), [('Scenario', '<xml/>')])
        loader_mock.assert_called_once_with('workbench/scenarios')

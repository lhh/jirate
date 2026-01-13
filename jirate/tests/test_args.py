#!/usr/bin/python3
"""
Comprehensive unit tests for ComplicatedArgs and GenericArgs classes
"""

import unittest
import argparse

# Add the project root to Python path so we can import jirate modules
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jirate.args import ComplicatedArgs, GenericArgs


class TestComplicatedArgs(unittest.TestCase):
    """Test cases for ComplicatedArgs class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.args = ComplicatedArgs()

    def test_initialization(self):
        """Test that ComplicatedArgs initializes correctly"""
        # Check that parser is an ArgumentParser instance
        self.assertIsInstance(self.args.parser(), argparse.ArgumentParser)
        
        # Check internal state
        self.assertEqual(self.args._commands, {})
        self.assertEqual(self.args._handlers, {})
        self.assertIsNone(self.args._subparsers)
        self.assertIsNone(self.args._parsed_ns)
        self.assertEqual(self.args._args, {})

    def test_add_argument(self):
        """Test adding arguments to the parser"""
        # Add an argument
        self.args.add_argument('--test', type=int, help='Test argument')
        
        # Parse arguments
        parsed_args = self.args.parse_args(args=['--test', '10'])
        self.assertEqual(parsed_args.test, 10)

    def test_add_arg(self):
        """Test adding additional arguments to namespace"""
        # Add an argument to the internal args dict
        self.args.add_arg('extra', 'value')
        
        # Create a namespace and finalize it
        ns = argparse.Namespace()
        self.args.finalize(ns)
        
        # Check that the extra argument was added to namespace
        self.assertTrue(hasattr(ns, 'extra'))
        self.assertEqual(ns.extra, 'value')

    def test_command_creation(self):
        """Test creating commands with subparsers"""
        # Create a command
        parser = self.args.command('test', help='Test command')
        
        # Verify the command was added
        self.assertIn('test', self.args._commands)
        self.assertIsNotNone(self.args._subparsers)
        
        # Verify parser is an ArgumentParser instance
        self.assertIsInstance(parser, argparse.ArgumentParser)

    def test_command_with_handler(self):
        """Test command with handler registration"""
        # Define a mock handler function
        def mock_handler(ns):
            return "handler_result"
        
        # Create command with handler
        self.args.command('test', help='Test command', handler=mock_handler)
        
        # Parse and finalize
        parsed_args = self.args.parse_args(args=['test'])
        result = self.args.finalize(parsed_args)
        
        # Verify handler was called
        self.assertEqual(result, "handler_result")

    def test_multiple_commands(self):
        """Test creating multiple commands"""
        # Create two commands with different handlers
        def handler_one(ns):
            return "first_result"
        
        def handler_two(ns):
            return "second_result"
        
        self.args.command('first', help='First command', handler=handler_one)
        self.args.command('second', help='Second command', handler=handler_two)
        
        # Test first command
        parsed_args = self.args.parse_args(args=['first'])
        result = self.args.finalize(parsed_args)
        self.assertEqual(result, "first_result")
        
        # Test second command
        parsed_args = self.args.parse_args(args=['second'])
        result = self.args.finalize(parsed_args)
        self.assertEqual(result, "second_result")

    def test_command_duplicate_error(self):
        """Test that duplicate commands raise ValueError"""
        # Create first command
        self.args.command('test')
        
        # Try to create duplicate - should raise ValueError
        with self.assertRaises(ValueError):
            self.args.command('test')

    def test_register_handler_error(self):
        """Test that registering handler for undefined command raises ValueError"""
        # Try to register handler for non-existent command
        with self.assertRaises(ValueError):
            self.args.register_handler('undefined', lambda x: None)

    def test_delete_handler(self):
        """Test deleting handlers"""
        # Define mock handler
        def mock_handler(ns):
            return "handler_result"
        
        # Create command with handler
        self.args.command('test', handler=mock_handler)
        
        # Verify handler exists
        parsed_args = self.args.parse_args(args=['test'])
        result = self.args.finalize(parsed_args)
        self.assertEqual(result, "handler_result")
        
        # Delete the handler
        self.args.delete_handler('test')
        
        # Handler should no longer be called
        result = self.args.finalize(parsed_args)
        self.assertIsNone(result)
        
        # Try to delete non-existent handler
        with self.assertRaises(ValueError):
            self.args.delete_handler('nonexistent')

    def test_parse_args(self):
        """Test parsing arguments"""
        # Add argument
        self.args.add_argument('--value', type=int)
        
        # Parse arguments
        parsed_args = self.args.parse_args(args=['--value', '5'])
        self.assertEqual(parsed_args.value, 5)

    def test_finalize_no_command(self):
        """Test finalize when no command is specified"""
        # Create namespace and finalize with default return value
        ns = argparse.Namespace()
        result = self.args.finalize(ns, 'default')
        self.assertEqual(result, 'default')

    def test_namespace_access(self):
        """Test accessing the parsed namespace"""
        # Add argument
        self.args.add_argument('--value', type=int)
        
        # Parse and finalize
        parsed_args = self.args.parse_args(args=['--value', '5'])
        self.args.finalize(parsed_args)
        
        # Access namespace through method
        ns = self.args.namespace()
        self.assertTrue(hasattr(ns, 'value'))
        self.assertEqual(ns.value, 5)

    def test_complex_command_with_arguments(self):
        """Test command with multiple arguments"""
        # Define a handler that uses parsed arguments
        def complex_handler(ns):
            return f"Command: {ns.command}, Value: {getattr(ns, 'value', 'not_set')}"
        
        # Create command with arguments
        cmd_parser = self.args.command('complex', help='Complex command')
        cmd_parser.add_argument('--value', type=str, default='default_value')
        
        # Parse and finalize
        parsed_args = self.args.parse_args(args=['complex', '--value', 'test_value'])
        result = self.args.finalize(parsed_args)
        
        # Verify result contains expected values
        self.assertIn("Command: complex", result)
        self.assertIn("Value: test_value", result)

    def test_empty_namespace_handling(self):
        """Test handling of empty namespace"""
        # Create empty namespace and finalize
        ns = argparse.Namespace()
        result = self.args.finalize(ns)
        
        # Should return None since no command was specified
        self.assertIsNone(result)

    def test_attribute_error_handling(self):
        """Test handling of attribute errors in finalize"""
        # Create namespace without command attribute
        ns = argparse.Namespace()
        
        # This should not raise an exception due to the try/except block
        result = self.args.finalize(ns)
        
        # Should return None since no command was specified
        self.assertIsNone(result)


class TestGenericArgs(unittest.TestCase):
    """Test cases for GenericArgs class"""

    def test_generic_args_initialization(self):
        """Test GenericArgs initialization"""
        generic_args = GenericArgs()
        self.assertIsInstance(generic_args, dict)

    def test_generic_args_set_and_get(self):
        """Test setting and getting attributes"""
        generic_args = GenericArgs()

        # Test setting via attribute
        generic_args.test_attr = "test_value"
        self.assertEqual(generic_args['test_attr'], "test_value")

        # Test getting via attribute
        self.assertEqual(generic_args.test_attr, "test_value")

    def test_generic_args_deletion(self):
        """Test deletion of attributes"""
        generic_args = GenericArgs()

        # Set attribute
        generic_args.test_attr = "test_value"
        self.assertEqual(generic_args.test_attr, "test_value")

        # Delete attribute
        del generic_args['test_attr']
        self.assertIsNone(generic_args.test_attr)

    def test_generic_args_missing_attribute(self):
        """Test handling of missing attributes"""
        generic_args = GenericArgs()

        # Missing attribute should return None
        self.assertIsNone(generic_args.nonexistent)

    def test_generic_args_multiple_attributes(self):
        """Test multiple attributes"""
        generic_args = GenericArgs()

        # Set multiple attributes
        generic_args.name = "test"
        generic_args.count = 42
        generic_args.active = True

        # Verify all can be accessed
        self.assertEqual(generic_args.name, "test")
        self.assertEqual(generic_args.count, 42)
        self.assertEqual(generic_args.active, True)


if __name__ == '__main__':
    unittest.main()

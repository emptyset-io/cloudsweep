import os
import importlib
import inspect
from utils.logger import get_logger
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, Type
import sys

# Assuming this logger is set up somewhere
import logging
logger = get_logger(__name__)

class ResourceScannerRegistry(ABC):
    """
    Represents a centralized registry for resource scanners. Scanners are registered
    as classes and are dynamically added to the registry.
    """

    # Centralized registry for all scanners, keyed by argument_name
    _registry: Dict[str, Type["ResourceScannerRegistry"]] = {}

    def __init__(self, name: str, argument_name: str, label: str):
        """
        Initializes a resource scanner with a name, argument name, and label.

        :param name: Unique name of the resource type (e.g., "EC2 Instances").
        :param argument_name: The short name for user arguments (e.g., "cloudformation").
        :param label: A unique label identifying the scanner (e.g., "CloudFormation").
        """
        self.name = name
        self.argument_name = argument_name
        self.label = label
        logger.debug(f"Scanner '{name}[{label}]' initialized.")

    @classmethod
    def add_scanner(cls, scanner_class: Type["ResourceScannerRegistry"]):
        """
        Adds a new scanner class to the registry, using the argument_name as the key.

        :param scanner_class: A subclass of ResourceScannerRegistry to be registered.
        """
        if not issubclass(scanner_class, ResourceScannerRegistry):
            raise ValueError("The scanner must be a subclass of ResourceScannerRegistry.")
        
        # Register the scanner by its argument_name, which is set in the subclass
        argument_name = scanner_class.argument_name  # Access the argument_name from the subclass
        cls._registry[argument_name] = scanner_class
        logger.debug(f"Scanner class '{scanner_class.__name__}' with argument name '{argument_name}' added to the registry.")
    @classmethod
    def get_scanner(cls, identifier: str) -> Type["ResourceScannerRegistry"]:
        """
        Retrieves a registered scanner class by its argument_name, label, or class name.

        :param identifier: The short name of the scanner class, its label, or its class name to retrieve.
        :return: The corresponding ResourceScannerRegistry subclass.
        """
        # First, check the registry by argument_name
        scanner_class = cls._registry.get(identifier)
        
        if scanner_class:
            logger.debug(f"Retrieved scanner class for argument_name '{identifier}': {scanner_class}")
            return scanner_class

        # If not found by argument_name, try finding it by label
        for scanner in cls._registry.values():
            if scanner.label == identifier:
                logger.debug(f"Retrieved scanner class for label '{identifier}': {scanner}")
                return scanner

        # If not found by argument_name or label, try matching by class name
        for scanner in cls._registry.values():
            if scanner.__name__.lower() == identifier.lower():
                logger.debug(f"Retrieved scanner class for class name '{identifier}': {scanner}")
                return scanner

        # If no match is found, raise an error
        raise ValueError(f"Scanner with identifier '{identifier}' not found (by class name, argument_name, or label).")

    
    @classmethod
    def list_scanners(cls):
        """
        Returns a sorted list of all registered scanner argument_names in alphabetical order.

        :return: A list of scanner argument_names sorted alphabetically.
        """
        argument_names = sorted(cls._registry.keys())  # Get and sort the scanner argument names
        logger.debug(f"Retrieved sorted scanner argument names: {argument_names}")
        return argument_names

    @classmethod
    def register_scanners_from_directory(cls, scanner_dir: str):
        """
        Automatically discovers and registers all scanner classes in a given directory.

        :param scanner_dir: Directory path where scanner modules are located.
        """
        scanner_path = Path(scanner_dir)
        
        # Ensure the directory exists and is valid
        if not scanner_path.exists() or not scanner_path.is_dir():
            raise ValueError(f"The directory '{scanner_dir}' does not exist or is not a directory.")

        original_sys_path = sys.path[:]  # Backup the original sys.path
        sys.path.append(str(scanner_path.parent))  # Add the parent directory to sys.path
        
        try:
            for filename in os.listdir(scanner_path):
                if filename.endswith(".py") and filename != "__init__.py":
                    module_name = filename[:-3]  # Strip the ".py" extension
                    try:
                        # Dynamically import the module
                        module = importlib.import_module(f"{scanner_dir.replace(os.sep, '.')}.{module_name}")
                        
                        # Iterate over all classes in the module
                        for name, obj in inspect.getmembers(module, inspect.isclass):
                            # Identify and register subclasses of ResourceScannerRegistry
                            if issubclass(obj, ResourceScannerRegistry) and obj is not ResourceScannerRegistry:
                                argument_name = getattr(obj, 'argument_name', None)
                                if argument_name:
                                    cls.add_scanner(obj)
                                    logger.debug(
                                        f"Registered scanner class '{obj.__name__}' with argument name '{argument_name}' from module '{module_name}'."
                                    )
                                else:
                                    logger.error(f"Class {obj.__name__} does not have an argument_name attribute.")
                    except Exception as e:
                        logger.error(f"Error importing module {module_name}: {e}")
        finally:
            sys.path = original_sys_path  # Restore sys.path to its original state


    @abstractmethod
    def scan(self, *args, **kwargs):
        """
        Abstract method to scan resources. Must be implemented by subclasses.
        """
        pass

    def __repr__(self):
        return f"ResourceScannerRegistry(name='{self.name}', argument_name='{self.argument_name}', label='{self.label}')"

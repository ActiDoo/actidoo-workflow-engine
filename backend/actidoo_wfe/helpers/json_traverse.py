# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy

import wrapt


def get_position_tracker(data, is_debugging = False):
    """
    Returns a position tracker for a nested dictionary or list.
    
    The position tracker allows you to traverse the data structure while keeping track of
    the current path in the hierarchy. This is useful for scenarios like validating JSON data
    where the context of a field (i.e., its position) is important.
    
    Args:
        data (dict or list): The nested data structure to track.
    
    Returns:
        tuple: A tuple containing:
            - position (list): The current path in the data structure as a list of keys/indices.
            - tracker (PositionTracker): A proxy object for the data that updates the position as you traverse it.
    """
    
    position = []
    tracker_counter = 0
    deepcopy_counter = 0

    class PositionTracker(wrapt.ObjectProxy):
        """
        A proxy class that tracks the current position within a nested dictionary or list.
        
        This class wraps the original data structure and intercepts item access to update
        the position path accordingly.
        """
        
        def __init__(self, data, path: list=[]):
            super().__init__(data)
            self._self_path = path
            self._self_tracker_map = {}
            
            if is_debugging:
                nonlocal tracker_counter
                tracker_counter= tracker_counter + 1
                print(tracker_counter)

        def __getitem__(self, key):
            """
            Intercepts access to dictionary or list items and updates the position path.
            
            If the accessed item is a dictionary or list, a new PositionTracker instance is returned,
            allowing further tracking of nested paths.
            
            Args:
                key (int or str): The key (for dicts) or index (for lists) being accessed.
            
            Returns:
                The accessed value, either directly or wrapped in a PositionTracker if it's a nested structure.
            """
            value = self.__wrapped__[key]
            nonlocal position
            
            def set_position():
                # Do not make a new assignment to 'position' here, i.e. DO NOT do this:
                # position  = self._self_path + [key]
                # otherwise 'position' will hold a new reference.
                # Then the caller of get_position_tracker will still work with the old reference and its old value.
                position.clear()
                position.extend(self._self_path)

            if isinstance(value, (list, dict)): # then it is a nested strucure, we have to "go deeper"
                set_position()
                if key in self._self_tracker_map:
                    return self._self_tracker_map[key]
                else:
                     self._self_tracker_map[key] = PositionTracker(value, self._self_path + [key])
                     return self._self_tracker_map[key]
            else:
                set_position()
                return value

        def __repr__(self):
            return repr(self.__wrapped__)
        
        def __deepcopy__(self, memo):
            """
            Supports deep copying, but returns an untracked version of the data
            
            Args:
                memo (dict): Memoization dictionary for deep copy.
            
            Returns:
                Any: A deep copy of the wrapped data.
            """
            if is_debugging:
                nonlocal deepcopy_counter
                deepcopy_counter = deepcopy_counter + 1
                print("deepcopy_counter %s", deepcopy_counter)
            
            return copy.deepcopy(self.__wrapped__, memo)
        
    return position, PositionTracker(data)

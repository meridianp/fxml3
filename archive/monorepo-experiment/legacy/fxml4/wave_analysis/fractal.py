"""Fractal degree handling for Elliott Wave analysis.

This module provides utilities for working with Elliott Wave patterns
across multiple timeframes, following the fractal nature of markets.
"""

from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer


class FractalDegreeHandler:
    """Handles nested waves of different fractal degrees in Elliott Wave analysis.
    
    Elliott Wave Theory recognizes that market patterns exist in a fractal structure,
    where the same patterns appear at different scales (degrees). This class handles
    the identification and tracking of waves across multiple timeframes.
    
    Degrees from largest to smallest:
    1. Grand Supercycle
    2. Supercycle
    3. Cycle
    4. Primary
    5. Intermediate
    6. Minor
    7. Minute
    8. Minuette
    9. Subminuette
    """
    
    # Define timeframe mappings to degrees
    DEGREE_TIMEFRAME_MAP = {
        "Grand Supercycle": "yearly",
        "Supercycle": "quarterly",
        "Cycle": "monthly",
        "Primary": "weekly",
        "Intermediate": "daily",
        "Minor": "4h",
        "Minute": "1h",
        "Minuette": "15m",
        "Subminuette": "5m"
    }
    
    # Labels used for different degrees
    DEGREE_LABELS = {
        "Grand Supercycle": ["I", "II", "III", "IV", "V", "a", "b", "c"],
        "Supercycle": ["I", "II", "III", "IV", "V", "A", "B", "C"],
        "Cycle": ["I", "II", "III", "IV", "V", "A", "B", "C"],
        "Primary": ["1", "2", "3", "4", "5", "A", "B", "C"],
        "Intermediate": ["(1)", "(2)", "(3)", "(4)", "(5)", "(A)", "(B)", "(C)"],
        "Minor": ["i", "ii", "iii", "iv", "v", "a", "b", "c"],
        "Minute": ["1", "2", "3", "4", "5", "a", "b", "c"],
        "Minuette": ["[i]", "[ii]", "[iii]", "[iv]", "[v]", "[a]", "[b]", "[c]"],
        "Subminuette": ["⒈", "⒉", "⒊", "⒋", "⒌", "ⓐ", "ⓑ", "ⓒ"]
    }
    
    def __init__(
        self,
        base_timeframe: str = "daily",
        higher_degrees: int = 1,
        lower_degrees: int = 2,
        wave_analyzers: Optional[Dict[str, ElliottWaveAnalyzer]] = None
    ):
        """Initialize the FractalDegreeHandler.
        
        Args:
            base_timeframe: Base timeframe for analysis (default: 'daily')
            higher_degrees: Number of higher degree timeframes to analyze
            lower_degrees: Number of lower degree timeframes to analyze
            wave_analyzers: Dictionary of ElliottWaveAnalyzer instances for each timeframe
        """
        self.base_timeframe = base_timeframe
        self.higher_degrees = higher_degrees
        self.lower_degrees = lower_degrees
        
        # Determine base degree based on timeframe
        self.base_degree = self._get_degree_from_timeframe(base_timeframe)
        
        # Initialize wave analyzers if not provided
        if wave_analyzers is None:
            self.wave_analyzers = self._initialize_analyzers()
        else:
            self.wave_analyzers = wave_analyzers
            
        # Stores the wave patterns for each timeframe
        self.wave_patterns = {}
        
        # Stores the relationships between waves of different degrees
        self.wave_relationships = {}
        
    def _get_degree_from_timeframe(self, timeframe: str) -> str:
        """Map a timeframe to its corresponding Elliott Wave degree.
        
        Args:
            timeframe: The timeframe (e.g., 'daily', '4h', '1h')
            
        Returns:
            The corresponding degree name
        """
        # Reverse mapping from timeframe to degree
        for degree, tf in self.DEGREE_TIMEFRAME_MAP.items():
            if tf == timeframe:
                return degree
                
        # Default to Intermediate if not found
        return "Intermediate"
        
    def _get_timeframe_from_degree(self, degree: str) -> str:
        """Get the timeframe for a given degree.
        
        Args:
            degree: The Elliott Wave degree
            
        Returns:
            The corresponding timeframe
        """
        return self.DEGREE_TIMEFRAME_MAP.get(degree, "daily")
        
    def _initialize_analyzers(self) -> Dict[str, ElliottWaveAnalyzer]:
        """Initialize Elliott Wave analyzers for each timeframe.
        
        Returns:
            Dictionary of analyzers for each timeframe
        """
        analyzers = {}
        
        # Get all degrees to analyze
        degrees = self._get_degrees_to_analyze()
        
        # Create an analyzer for each degree's timeframe
        for degree in degrees:
            timeframe = self._get_timeframe_from_degree(degree)
            
            # Configure analyzer parameters based on timeframe
            # Higher timeframes need larger detection windows
            if timeframe in ["yearly", "quarterly", "monthly"]:
                window = 8
                min_length = 4
            elif timeframe in ["weekly", "daily"]:
                window = 5
                min_length = 3
            else:
                window = 3
                min_length = 2
                
            analyzers[timeframe] = ElliottWaveAnalyzer(
                peak_detection_window=window,
                min_wave_length=min_length,
                fib_tolerance=0.15  # Consistent across timeframes
            )
            
        return analyzers
    
    def _get_degrees_to_analyze(self) -> List[str]:
        """Get the list of degrees to analyze based on configuration.
        
        Returns:
            List of degree names
        """
        # Get ordered list of all degrees
        all_degrees = list(self.DEGREE_TIMEFRAME_MAP.keys())
        
        # Find index of base degree
        try:
            base_idx = all_degrees.index(self.base_degree)
        except ValueError:
            base_idx = all_degrees.index("Intermediate")  # Default
            
        # Calculate degree range to analyze
        start_idx = max(0, base_idx - self.higher_degrees)
        end_idx = min(len(all_degrees), base_idx + self.lower_degrees + 1)
        
        return all_degrees[start_idx:end_idx]
    
    def analyze_timeframes(
        self,
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, Dict]:
        """Analyze multiple timeframes and detect wave patterns.
        
        Args:
            data_dict: Dictionary mapping timeframes to price DataFrames
            
        Returns:
            Dictionary of wave patterns for each timeframe
        """
        results = {}
        
        # Analyze each timeframe
        for timeframe, df in data_dict.items():
            if timeframe in self.wave_analyzers:
                analyzer = self.wave_analyzers[timeframe]
                wave_points = analyzer.detect_waves(df)
                
                if wave_points:
                    # Label data with wave annotations
                    labeled_df = analyzer.label_chart_data(df, wave_points)
                    
                    # Store results
                    results[timeframe] = {
                        "wave_points": wave_points,
                        "labeled_data": labeled_df,
                        "degree": self._get_degree_from_timeframe(timeframe)
                    }
        
        # Store wave patterns
        self.wave_patterns = results
        
        # Determine relationships between waves of different degrees
        self._identify_nested_structures()
        
        return results
    
    def _identify_nested_structures(self) -> Dict:
        """Identify nested wave structures across timeframes.
        
        This method analyzes the detected waves across different timeframes
        to identify how waves of lower degrees nest within waves of higher degrees.
        
        Returns:
            Dictionary of wave relationships
        """
        relationships = {}
        
        # Get ordered list of timeframes from smallest to largest
        ordered_timeframes = []
        for degree in reversed(list(self.DEGREE_TIMEFRAME_MAP.keys())):
            timeframe = self._get_timeframe_from_degree(degree)
            if timeframe in self.wave_patterns:
                ordered_timeframes.append(timeframe)
        
        # For each timeframe (except the largest)
        for i in range(len(ordered_timeframes) - 1):
            lower_tf = ordered_timeframes[i]
            higher_tf = ordered_timeframes[i + 1]
            
            lower_patterns = self.wave_patterns[lower_tf]
            higher_patterns = self.wave_patterns[higher_tf]
            
            # Skip if no patterns in either timeframe
            if not lower_patterns["wave_points"] or not higher_patterns["wave_points"]:
                continue
                
            # For each higher degree wave, find lower degree waves that fit inside it
            higher_labeled = higher_patterns["labeled_data"]
            lower_labeled = lower_patterns["labeled_data"]
            
            # Get wave columns from the labeled data
            higher_wave_cols = [col for col in higher_labeled.columns if col.startswith("impulse_") or col.startswith("corrective_")]
            lower_wave_cols = [col for col in lower_labeled.columns if col.startswith("impulse_") or col.startswith("corrective_")]
            
            # For each higher wave
            for h_col in higher_wave_cols:
                # Get wave start and end timestamps
                higher_waves = higher_labeled[higher_labeled[h_col] > 0]
                
                for h_wave_num in higher_waves[h_col].unique():
                    # Extract this specific wave
                    h_wave = higher_waves[higher_waves[h_col] == h_wave_num]
                    
                    if len(h_wave) < 2:
                        continue
                        
                    # Get start and end timestamps
                    h_start = h_wave.index[0]
                    h_end = h_wave.index[-1]
                    
                    # Find lower timeframe waves that fit inside this range
                    nested_waves = {}
                    
                    for l_col in lower_wave_cols:
                        # Filter lower timeframe to the date range
                        l_waves_in_range = lower_labeled[
                            (lower_labeled.index >= h_start) & 
                            (lower_labeled.index <= h_end) &
                            (lower_labeled[l_col] > 0)
                        ]
                        
                        # Group by wave number
                        for l_wave_num in l_waves_in_range[l_col].unique():
                            l_wave = l_waves_in_range[l_waves_in_range[l_col] == l_wave_num]
                            
                            if len(l_wave) >= 2:
                                wave_key = f"{l_col}_{l_wave_num}"
                                nested_waves[wave_key] = {
                                    "start": l_wave.index[0],
                                    "end": l_wave.index[-1],
                                    "type": "impulse" if l_col.startswith("impulse") else "corrective",
                                    "number": int(l_wave_num)
                                }
                    
                    # Store relationship
                    rel_key = f"{h_col}_{h_wave_num}"
                    relationships[rel_key] = {
                        "higher_degree": {
                            "timeframe": higher_tf,
                            "degree": self._get_degree_from_timeframe(higher_tf),
                            "type": "impulse" if h_col.startswith("impulse") else "corrective",
                            "number": int(h_wave_num),
                            "start": h_start,
                            "end": h_end
                        },
                        "lower_degree_waves": nested_waves
                    }
        
        # Store relationships
        self.wave_relationships = relationships
        
        return relationships
    
    def get_wave_annotations(
        self,
        timeframe: str,
        wave_col: str,
        use_degree_labels: bool = True
    ) -> Dict[int, str]:
        """Get appropriate wave annotations for a specific timeframe.
        
        Args:
            timeframe: Timeframe to get annotations for
            wave_col: Column name of the wave pattern
            use_degree_labels: Whether to use degree-specific labels
            
        Returns:
            Dictionary mapping wave numbers to appropriate labels
        """
        if timeframe not in self.wave_patterns:
            return {}
            
        degree = self._get_degree_from_timeframe(timeframe)
        
        # Determine if impulse or corrective
        is_impulse = wave_col.startswith("impulse")
        
        # Get appropriate labels based on degree
        if use_degree_labels:
            if is_impulse:
                labels = self.DEGREE_LABELS[degree][:5]  # First 5 are impulse
            else:
                labels = self.DEGREE_LABELS[degree][5:8]  # Last 3 are corrective
        else:
            # Use standard 1-2-3-4-5 or A-B-C
            if is_impulse:
                labels = ["1", "2", "3", "4", "5"]
            else:
                labels = ["A", "B", "C"]
                
        # Map wave numbers to labels
        return {i+1: label for i, label in enumerate(labels)}
    
    def label_nested_waves(
        self,
        df: pd.DataFrame,
        timeframe: str,
        show_higher_degree: bool = True,
        show_lower_degree: bool = True
    ) -> pd.DataFrame:
        """Label DataFrame with nested wave structure information.
        
        Args:
            df: DataFrame to label
            timeframe: Current timeframe being labeled
            show_higher_degree: Whether to include higher degree information
            show_lower_degree: Whether to include lower degree information
            
        Returns:
            DataFrame with nested wave labels
        """
        if timeframe not in self.wave_patterns:
            return df
            
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        degree = self._get_degree_from_timeframe(timeframe)
        
        # Add degree information
        result_df["wave_degree"] = degree
        
        # Add column to show the position within higher degree waves
        if show_higher_degree:
            result_df["higher_degree_wave"] = ""
            result_df["higher_degree_position"] = ""
            
            # Find relationships where this timeframe is the lower degree
            higher_relationships = [
                rel for rel, data in self.wave_relationships.items()
                if data["higher_degree"]["timeframe"] != timeframe and 
                   any(wave for wave_key, wave in data["lower_degree_waves"].items() 
                       if timeframe in self.wave_patterns)
            ]
            
            for rel in higher_relationships:
                rel_data = self.wave_relationships[rel]
                higher_info = rel_data["higher_degree"]
                
                # Get higher degree wave label
                higher_degree = higher_info["degree"]
                higher_type = higher_info["type"]
                higher_number = higher_info["number"]
                
                if higher_type == "impulse":
                    higher_label = self.DEGREE_LABELS[higher_degree][higher_number - 1]
                else:
                    higher_label = self.DEGREE_LABELS[higher_degree][higher_number + 4]  # +4 to get to corrective waves
                
                # Find date range of higher degree wave
                higher_start = higher_info["start"]
                higher_end = higher_info["end"]
                
                # Label rows within this range
                mask = (result_df.index >= higher_start) & (result_df.index <= higher_end)
                result_df.loc[mask, "higher_degree_wave"] = f"{higher_degree} {higher_label}"
                
                # Calculate position within the higher degree wave (0-100%)
                total_duration = (higher_end - higher_start).total_seconds()
                if total_duration > 0:
                    result_df.loc[mask, "higher_degree_position"] = (
                        (result_df.index - higher_start).map(lambda x: x.total_seconds()) / total_duration * 100
                    )
        
        # Add column to show the constituent lower degree waves
        if show_lower_degree and self.wave_relationships:
            result_df["lower_degree_waves"] = ""
            
            # Find relationships where this timeframe is the higher degree
            lower_relationships = [
                rel for rel, data in self.wave_relationships.items()
                if data["higher_degree"]["timeframe"] == timeframe
            ]
            
            for rel in lower_relationships:
                rel_data = self.wave_relationships[rel]
                higher_info = rel_data["higher_degree"]
                lower_waves = rel_data["lower_degree_waves"]
                
                # Skip if no lower waves
                if not lower_waves:
                    continue
                    
                # Get higher degree wave information
                h_type = higher_info["type"]
                h_number = higher_info["number"]
                h_col = f"{'impulse' if h_type == 'impulse' else 'corrective'}_wave"
                
                # Find all rows in this higher degree wave
                mask = (result_df[h_col] == h_number)
                
                # Create a summary of lower degree waves
                lower_summary = []
                for wave_key, wave_info in lower_waves.items():
                    lower_tf = wave_info["timeframe"] if "timeframe" in wave_info else "lower"
                    lower_type = wave_info["type"]
                    lower_number = wave_info["number"]
                    
                    lower_summary.append(f"{lower_tf} {lower_type} {lower_number}")
                
                # Add summary to DataFrame
                if lower_summary:
                    result_df.loc[mask, "lower_degree_waves"] = ", ".join(lower_summary)
        
        return result_df
    
    def get_complete_wave_structure(self) -> Dict:
        """Get the complete nested wave structure across all timeframes.
        
        Returns:
            Dictionary with the complete wave structure
        """
        if not self.wave_patterns or not self.wave_relationships:
            return {}
            
        # Find the highest degree timeframe with patterns
        ordered_degrees = list(self.DEGREE_TIMEFRAME_MAP.keys())
        highest_degree = None
        
        for degree in ordered_degrees:
            timeframe = self._get_timeframe_from_degree(degree)
            if timeframe in self.wave_patterns and self.wave_patterns[timeframe]["wave_points"]:
                highest_degree = degree
                highest_timeframe = timeframe
                break
                
        if not highest_degree:
            return {}
            
        # Start with the highest degree waves
        highest_patterns = self.wave_patterns[highest_timeframe]
        highest_labeled = highest_patterns["labeled_data"]
        
        # Get wave columns
        wave_cols = [col for col in highest_labeled.columns 
                     if col.startswith("impulse_") or col.startswith("corrective_")]
        
        # Build the structure recursively
        structure = {}
        
        for col in wave_cols:
            wave_type = "impulse" if col.startswith("impulse") else "corrective"
            
            # Get unique wave numbers
            for wave_num in highest_labeled[highest_labeled[col] > 0][col].unique():
                # Extract this wave
                wave = highest_labeled[highest_labeled[col] == wave_num]
                
                if len(wave) < 2:
                    continue
                    
                # Wave information
                wave_key = f"{col}_{wave_num}"
                
                # Find its structure in relationships
                if wave_key in self.wave_relationships:
                    structure[wave_key] = self._build_wave_structure(wave_key)
                else:
                    structure[wave_key] = {
                        "degree": highest_degree,
                        "timeframe": highest_timeframe,
                        "type": wave_type,
                        "number": int(wave_num),
                        "start": wave.index[0],
                        "end": wave.index[-1],
                        "subwaves": {}
                    }
        
        return structure
    
    def _build_wave_structure(self, wave_key: str) -> Dict:
        """Recursively build the structure of a wave and its subwaves.
        
        Args:
            wave_key: Key of the wave in the relationships dictionary
            
        Returns:
            Dictionary with the wave structure
        """
        if wave_key not in self.wave_relationships:
            return {}
            
        rel_data = self.wave_relationships[wave_key]
        higher_info = rel_data["higher_degree"]
        lower_waves = rel_data["lower_degree_waves"]
        
        # Build structure for this wave
        structure = {
            "degree": higher_info["degree"],
            "timeframe": higher_info["timeframe"],
            "type": higher_info["type"],
            "number": higher_info["number"],
            "start": higher_info["start"],
            "end": higher_info["end"],
            "subwaves": {}
        }
        
        # Add subwaves
        for subwave_key, subwave_info in lower_waves.items():
            # Check if this subwave also has relationships
            if subwave_key in self.wave_relationships:
                structure["subwaves"][subwave_key] = self._build_wave_structure(subwave_key)
            else:
                structure["subwaves"][subwave_key] = {
                    "degree": self._get_degree_from_timeframe(subwave_info.get("timeframe", "lower")),
                    "timeframe": subwave_info.get("timeframe", "lower"),
                    "type": subwave_info["type"],
                    "number": subwave_info["number"],
                    "start": subwave_info["start"],
                    "end": subwave_info["end"],
                    "subwaves": {}
                }
        
        return structure
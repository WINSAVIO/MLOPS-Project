"use client";

import { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { ComposableMap, Geographies, Geography, ZoomableGroup } from 'react-simple-maps';
import styles from './page.module.css';

// Mocked 14-Day Baseline Forecast for UI testing
const MOCK_14_DAY_BASELINE = Array.from({ length: 14 }).map((_, i) => {
  const base_mw = Math.floor(200000 + ((i * 12345) % 50000));
  return {
    date: `0${(i % 9) + 7}/05/2026\n${['Thu', 'Fri', 'Sat', 'Sun', 'Mon', 'Tue', 'Wed'][i % 7]}`,
    baseline_mw: base_mw,
    original_baseline_mw: base_mw,
    features: {
      max_temperature: Math.floor((30 + ((i * 7) % 15)) * 10) / 10,
      humidity: Math.floor(40 + ((i * 13) % 40)),
      cloud_cover: Math.floor((i * 17) % 100),
      precipitation: Math.floor((i * 3) % 20),
      evapotranspiration: Math.floor((2 + ((i * 1.5) % 5)) * 10) / 10,
      is_holiday: i % 7 === 3 // Sunday is holiday
    }
  };
});

export default function Home() {
  const [viewMode, setViewMode] = useState('national'); // 'national' | 'state'
  const [selectedState, setSelectedState] = useState('All-India');
  const [hoveredState, setHoveredState] = useState('');
  const [shapData, setShapData] = useState(null);
  
  const [isTimelineOpen, setIsTimelineOpen] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  
  const [forecastData, setForecastData] = useState(MOCK_14_DAY_BASELINE);
  const [selectedDayIdx, setSelectedDayIdx] = useState(0);
  
  const [scenario, setScenario] = useState(MOCK_14_DAY_BASELINE[0].features);

  const handleDayClick = (data, index) => {
    if(index !== undefined) {
      setSelectedDayIdx(index);
      setScenario(forecastData[index].features);
    }
  };

  const handleSliderChange = (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : parseFloat(e.target.value);
    setScenario({ ...scenario, [e.target.name]: value });
  };

  const handlePredict = async () => {
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/api/predict/scenario?state_name=${encodeURIComponent(selectedState)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date_index: selectedDayIdx,
          max_temperature: scenario.max_temperature,
          humidity: scenario.humidity,
          cloud_cover: scenario.cloud_cover,
          precipitation: scenario.precipitation,
          evapotranspiration: scenario.evapotranspiration,
          is_holiday: scenario.is_holiday,
          current_baseline_mw: forecastData[selectedDayIdx].original_baseline_mw
        })
      });
      const data = await response.json();
      
      const newData = [...forecastData];
      newData[selectedDayIdx] = {
        ...newData[selectedDayIdx],
        baseline_mw: Math.floor(data.predicted_mw)
      };
      setForecastData(newData);
      setShapData(data.shap_values);
    } catch (err) {
      console.error(err);
    }
  };

  const handleStateClick = (stateName) => {
    setSelectedState(stateName);
    setViewMode('state');
    
    // Generate distinct state baseline AND climate features
    const stateHash = stateName.charCodeAt(0) + stateName.charCodeAt(stateName.length - 1);
    const scaleFactor = ((stateHash * 7) % 50 + 10) / 100; 
    
    // Geographically realistic temperatures
    const isColdState = ['Jammu & Kashmir', 'Himachal Pradesh', 'Uttarakhand', 'Sikkim', 'Arunachal Pradesh', 'Ladakh'].includes(stateName);
    const isHotState = ['Rajasthan', 'Gujarat', 'Madhya Pradesh', 'Maharashtra', 'Uttar Pradesh'].includes(stateName);
    
    let tempOffset = (stateHash % 10) - 5; 
    if (isColdState) tempOffset -= 15; // Drop temps heavily
    if (isHotState) tempOffset += 5; // Raise temps
    
    const stateForecast = MOCK_14_DAY_BASELINE.map(day => {
        const generatedTemp = Math.floor((day.features.max_temperature + tempOffset) * 10) / 10;
        return {
            ...day,
            baseline_mw: Math.floor(day.original_baseline_mw * scaleFactor),
            original_baseline_mw: Math.floor(day.original_baseline_mw * scaleFactor),
            features: {
               ...day.features,
               max_temperature: Math.min(43, Math.max(-5, generatedTemp)), // Clamp between -5C and 43C
               humidity: Math.floor(Math.min(100, Math.max(0, day.features.humidity + tempOffset * 2)))
            }
        };
    });
    setForecastData(stateForecast);
    setScenario(stateForecast[selectedDayIdx].features); // Instantly update sliders!
    setShapData(null);
  };

  const handleReset = () => {
    setScenario(MOCK_14_DAY_BASELINE[selectedDayIdx].features);
  };

  const handleMapDoubleClick = () => {
    setViewMode('national');
    setSelectedState('All-India');
    setForecastData(MOCK_14_DAY_BASELINE);
    setScenario(MOCK_14_DAY_BASELINE[selectedDayIdx].features);
    setShapData(null);
  };

  const getHeatmapColor = (stateName) => {
    const safeName = String(stateName || "Unknown");
    
    // Calculate mathematically accurate mock consumption for this state on the selected day
    const stateHash = safeName.charCodeAt(0) + safeName.charCodeAt(safeName.length - 1);
    const scaleFactor = ((stateHash * 7) % 50 + 10) / 100;
    
    const natConsumption = MOCK_14_DAY_BASELINE[selectedDayIdx]?.original_baseline_mw || 200000;
    const stateConsumption = natConsumption * scaleFactor;
    
    // Map actual MW consumption to heatmap threshold buckets
    let demandFactor = 0;
    if (stateConsumption > 100000) demandFactor = 4;
    else if (stateConsumption > 80000) demandFactor = 3;
    else if (stateConsumption > 60000) demandFactor = 2;
    else if (stateConsumption > 40000) demandFactor = 1;
    
    // Heatmap Colors (Low to High Energy Demand)
    const colors = ["#fef08a", "#fde047", "#f59e0b", "#ef4444", "#b91c1c"];
    return colors[demandFactor];
  };

  return (
    <div className={styles.container}>
      
      {/* 14-Day Timeline (Top Bar) */}
      <header className={`${styles.topBar} ${isTimelineOpen ? styles.topBarOpen : styles.topBarClosed}`}>
        <div className={styles.headerRow}>
          <h2 className={styles.timelineTitle}>
            {isTimelineOpen ? `14-Day Forecast Timeline (${selectedState})` : `Dashboard: ${selectedState}`}
          </h2>
          <button className={styles.toggleBtn} onClick={() => setIsTimelineOpen(!isTimelineOpen)}>
            {isTimelineOpen ? '▲ Collapse Timeline' : '▼ Expand Timeline'}
          </button>
        </div>
        
        {isTimelineOpen && (
          <div className={styles.chartContainer}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecastData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis dataKey="date" stroke="#94a3b8" tick={{fontSize: 12}} />
                <YAxis stroke="#94a3b8" />
                <RechartsTooltip contentStyle={{backgroundColor: '#1e293b', border: '1px solid #475569'}} />
                <Line type="monotone" dataKey="baseline_mw" stroke="#3b82f6" strokeWidth={3} activeDot={{ r: 8, onClick: (e, payload) => { if(payload) handleDayClick(payload.payload, payload.index); } }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </header>

      <div className={styles.mainContent}>
        
        {/* Sidebar / Controls */}
        <aside className={`${styles.sidebar} ${isSidebarOpen ? styles.sidebarOpen : styles.sidebarClosed}`}>
          {isSidebarOpen && (
            <>
              <div>
                <h1 className={styles.title}>Scenario Editor</h1>
            <p className={styles.subtitle}>
              Editing <strong>{forecastData[selectedDayIdx].date.replace('\n', ' ')}</strong>
            </p>
          </div>

          <div className={styles.divider}></div>

          {/* Feature Sliders */}
          <div className={styles.controlGroup}>
            <label>Max Temperature (°C) <span>{scenario.max_temperature}</span></label>
            <input type="range" name="max_temperature" min="10" max="50" step="0.5" value={scenario.max_temperature} onChange={handleSliderChange} />
          </div>

          <div className={styles.controlGroup}>
            <label>Humidity (%) <span>{scenario.humidity}</span></label>
            <input type="range" name="humidity" min="0" max="100" step="1" value={scenario.humidity} onChange={handleSliderChange} />
          </div>

          <div className={styles.controlGroup}>
            <label>Cloud Cover (%) <span>{scenario.cloud_cover}</span></label>
            <input type="range" name="cloud_cover" min="0" max="100" step="1" value={scenario.cloud_cover} onChange={handleSliderChange} />
          </div>

          <div className={styles.controlGroup}>
            <label>Precipitation (mm) <span>{scenario.precipitation}</span></label>
            <input type="range" name="precipitation" min="0" max="200" step="1" value={scenario.precipitation} onChange={handleSliderChange} />
          </div>

          <div className={styles.controlGroup}>
            <label>Evapotranspiration <span>{scenario.evapotranspiration}</span></label>
            <input type="range" name="evapotranspiration" min="0" max="20" step="0.1" value={scenario.evapotranspiration} onChange={handleSliderChange} />
          </div>

          <div className={styles.controlGroup}>
            <label className={styles.checkboxLabel}>
              <input type="checkbox" name="is_holiday" checked={scenario.is_holiday} onChange={handleSliderChange} />
              Is Public Holiday
            </label>
          </div>

          {/* Action Buttons */}
          <div className={styles.buttonGroup}>
            <button className={styles.btnSecondary} onClick={handleReset}>Reset to Baseline</button>
            <button className={styles.btnPrimary} onClick={handlePredict}>Predict</button>
          </div>

          {/* SHAP Placeholder */}
          {viewMode === 'state' && (
            <div className={styles.shapContainer}>
              <h3 style={{marginTop: 0}}>Explainability (SHAP)</h3>
              {shapData ? (
                <div>
                  {Object.entries(shapData).map(([feature, impact]) => (
                    <div key={feature} style={{display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.9rem'}}>
                      <span style={{color: '#94a3b8'}}>{feature}</span>
                      <span style={{color: impact.includes('+') ? '#ef4444' : '#10b981', fontWeight: 'bold'}}>{impact}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className={styles.placeholderText}>Click Predict to calculate Real SHAP values...</p>
              )}
            </div>
          )}
            </>
          )}
        </aside>

        {/* Main Map Area */}
        <main className={styles.main}>
          {!isSidebarOpen && (
            <div className={styles.floatingToggle}>
              <button className={styles.toggleBtn} onClick={() => setIsSidebarOpen(true)}>
                ▶ Open Editor
              </button>
            </div>
          )}
          {isSidebarOpen && (
             <div className={styles.floatingToggle} style={{left: '-1rem'}}>
               {/* Just a tiny absolute close button if we want, but better place it in the sidebar. Let's just put it in the header. */}
             </div>
          )}
          
          {isSidebarOpen && (
            <button 
              className={styles.toggleBtn} 
              style={{position: 'absolute', top: '1rem', left: '1rem', zIndex: 100}} 
              onClick={() => setIsSidebarOpen(false)}
            >
              ◀ Close Editor
            </button>
          )}

          {/* Interactive Map Area */}
          <div style={{width: '100%', height: '100%', position: 'relative'}} onDoubleClick={handleMapDoubleClick}>
            
            {/* Map Title Feedback overlay - Moved to Top Right to avoid sidebar overlap */}
            <div style={{position: 'absolute', top: 20, right: 20, zIndex: 10, pointerEvents: 'none', textAlign: 'right'}}>
              <h2 style={{margin: 0, color: '#f8fafc', fontSize: '1.5rem', textShadow: '2px 2px 4px rgba(0,0,0,0.8)'}}>GridSight: India Energy Forecast</h2>
              <h3 style={{margin: 0, color: '#94a3b8', fontSize: '1.2rem', textShadow: '2px 2px 4px rgba(0,0,0,0.8)'}}>{forecastData[selectedDayIdx].date.replace('\n', ' ')}</h3>
            </div>
            
            {viewMode === 'national' ? (
               hoveredState && (
                <div style={{position: 'absolute', top: 100, right: 20, background: 'rgba(0,0,0,0.8)', padding: '10px 20px', borderRadius: '8px', zIndex: 100, border: '1px solid var(--accent)', pointerEvents: 'none'}}>
                  <h3 style={{margin: 0, color: 'white'}}>{hoveredState}</h3>
                  <p style={{margin: '5px 0 0 0', color: '#94a3b8'}}>Click to drill down</p>
                </div>
              )
            ) : (
               <div style={{position: 'absolute', top: 100, right: 20, background: 'rgba(0,0,0,0.8)', padding: '15px 25px', borderRadius: '8px', zIndex: 100, border: '2px solid #3b82f6'}}>
                  <h2 style={{margin: 0, color: '#60a5fa'}}>{selectedState}</h2>
                  <p style={{margin: '5px 0 0 0', color: '#94a3b8'}}>Double-click map to return to National View</p>
                </div>
            )}
            
            {/* key={selectedDayIdx} forces the SVG map to fully re-render so heatmap colors instantly change on day click! */}
            <ComposableMap key={selectedDayIdx} projection="geoMercator" projectionConfig={{ scale: 1000, center: [80, 22] }} style={{width: "100%", height: "100%"}}>
              {/* Removed hardcoded zoom so states are never cropped. User can drag/zoom freely. */}
              <ZoomableGroup zoom={1} center={[80, 22]}>
                <Geographies geography="/india.topo.json">
                  {({ geographies }) =>
                    geographies.map((geo) => {
                      const stateName = geo.properties.name || geo.properties.ST_NM || geo.id;
                      if (stateName === '-99') return null;
                      
                      const isSelected = viewMode === 'state' && selectedState === stateName;
                      const isDimmed = viewMode === 'state' && !isSelected;
                      
                      return (
                        <Geography
                          key={geo.rsmKey}
                          geography={geo}
                          onClick={() => handleStateClick(stateName)}
                          onMouseEnter={() => setHoveredState(stateName)}
                          onMouseLeave={() => setHoveredState('')}
                          style={{
                            default: { 
                              fill: getHeatmapColor(stateName), 
                              stroke: isSelected ? "#ffffff" : "#1e293b", 
                              strokeWidth: isSelected ? 2.5 : 0.5, 
                              opacity: isDimmed ? 0.3 : 1,
                              outline: "none", 
                              transition: 'all 250ms' 
                            },
                            hover: { fill: "#3b82f6", stroke: "#ffffff", strokeWidth: 2, opacity: 1, outline: "none", cursor: "pointer", transition: 'all 250ms' },
                            pressed: { fill: "#2563eb", outline: "none" }
                          }}
                        />
                      );
                    })
                  }
                </Geographies>
              </ZoomableGroup>
            </ComposableMap>
          </div>
        </main>
      </div>
    </div>
  );
}

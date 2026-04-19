import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Circle } from 'react-leaflet';
import { useNavigate } from 'react-router-dom';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';
import api from '../../api';
import Navbar from '../../components/shared/Navbar';
import Badge from '../../components/shared/Badge';
import Button from '../../components/shared/Button';
import { getImageUrl } from '../../utils/image';
import './MapView.css';

// ── Marker icons by status ─────────────────────────────────────────────────
const STATUS_COLORS = {
    pending:     '#ef4444',
    in_progress: '#f59e0b',
    resolved:    '#10b981',
};

const makeIcon = (color) => L.divIcon({
    className: '',
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
        <path d="M14 0C6.268 0 0 6.268 0 14c0 9.333 14 22 14 22S28 23.333 28 14C28 6.268 21.732 0 14 0z"
              fill="${color}" stroke="white" stroke-width="1.5"/>
        <circle cx="14" cy="14" r="5" fill="white" opacity="0.9"/>
    </svg>`,
    iconSize: [28, 36],
    iconAnchor: [14, 36],
    popupAnchor: [0, -38],
});

const ICONS = {
    pending:     makeIcon(STATUS_COLORS.pending),
    in_progress: makeIcon(STATUS_COLORS.in_progress),
    resolved:    makeIcon(STATUS_COLORS.resolved),
};

const SEVERITY_INTENSITY = { critical: 1.0, high: 0.8, medium: 0.5, low: 0.3 };

// ── Heatmap layer ──────────────────────────────────────────────────────────
function HeatmapLayer({ points, visible }) {
    const map = useMap();
    const ref = useRef(null);

    useEffect(() => {
        if (!visible) {
            if (ref.current) { ref.current.remove(); ref.current = null; }
            return;
        }
        if (!ref.current) {
            ref.current = L.heatLayer(points, { radius: 25, blur: 15, maxZoom: 17 }).addTo(map);
        }
        return () => { if (ref.current) { ref.current.remove(); ref.current = null; } };
    }, [visible, map, points]);

    return null;
}

// ── Locate Me controller ───────────────────────────────────────────────────
function LocateController({ trigger, onLocated, onError }) {
    const map = useMap();

    useEffect(() => {
        if (!trigger) return;
        if (!navigator.geolocation) { onError('Geolocation not supported.'); return; }

        navigator.geolocation.getCurrentPosition(
            ({ coords }) => {
                map.flyTo([coords.latitude, coords.longitude], 16, { animate: true, duration: 1.2 });
                onLocated([coords.latitude, coords.longitude]);
            },
            (err) => {
                const msgs = { 1: 'Permission denied.', 2: 'Location unavailable.', 3: 'Request timed out.' };
                onError(msgs[err.code] || 'Could not get location.');
            },
            { timeout: 10000 }
        );
    }, [trigger]);

    return null;
}

// ── Status badge variant ───────────────────────────────────────────────────
const statusVariant = (s = '') => {
    if (s === 'resolved')    return 'success';
    if (s === 'in_progress') return 'warning';
    if (s === 'pending')     return 'danger';
    return 'neutral';
};

const statusLabel = (s = '') =>
    ({ pending: 'Pending', in_progress: 'In Progress', resolved: 'Resolved' }[s] || s);

// ── Main component ─────────────────────────────────────────────────────────
const MapView = () => {
    const navigate = useNavigate();

    const [reports, setReports]       = useState([]);
    const [loading, setLoading]       = useState(true);
    const [showHeatmap, setShowHeatmap] = useState(false);
    const [filters, setFilters]       = useState({ pending: true, in_progress: true, resolved: true });
    const [locateTrigger, setLocateTrigger] = useState(1);
    const [locating, setLocating]     = useState(true);
    const [userPos, setUserPos]       = useState(null);
    const [toast, setToast]           = useState('');
    const [mapCenter, setMapCenter]   = useState([20.5937, 78.9629]); // India default
    const [sidebarSearch, setSidebarSearch] = useState('');

    // Fetch all reports
    useEffect(() => {
        api.get('/reports/')
            .then(({ data }) => {
                const valid = data.filter(r => r.latitude && r.longitude);
                setReports(valid);
                if (valid.length > 0) {
                    setMapCenter([valid[0].latitude, valid[0].longitude]);
                }
            })
            .catch(() => setReports([]))
            .finally(() => setLoading(false));
    }, []);

    const filteredReports = reports.filter(r => {
        if (!filters[r.status]) return false;
        if (sidebarSearch.trim()) {
            const q = sidebarSearch.toLowerCase();
            return r.title.toLowerCase().includes(q) || (r.description || '').toLowerCase().includes(q);
        }
        return true;
    });

    const heatPoints = filteredReports.map(r => [
        r.latitude,
        r.longitude,
        SEVERITY_INTENSITY[r.ai_severity_level || r.severity] ?? 0.5,
    ]);

    const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 3500); };

    const toggleFilter = (key) => setFilters(f => ({ ...f, [key]: !f[key] }));

    const handleLocate = () => { setLocating(true); setLocateTrigger(n => n + 1); };

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            <main className="map-view-container">
                {/* ── Sidebar ── */}
                <div className="map-sidebar">
                    <h2 className="text-xl mb-md">
                        Reports {!loading && <span className="reports-count">{filteredReports.length}</span>}
                    </h2>

                    {/* Status filters */}
                    <div className="map-filter-row">
                        {Object.entries({ pending: 'Pending', in_progress: 'In Progress', resolved: 'Resolved' }).map(([key, label]) => (
                            <button
                                key={key}
                                className={`map-filter-chip ${filters[key] ? 'active' : ''}`}
                                style={{ '--chip-color': STATUS_COLORS[key] }}
                                onClick={() => toggleFilter(key)}
                            >
                                <span className="chip-dot" />
                                {label}
                            </button>
                        ))}
                    </div>

                    {/* Sidebar search */}
                    <input
                        className="sidebar-search"
                        type="text"
                        placeholder="Search reports…"
                        value={sidebarSearch}
                        onChange={e => setSidebarSearch(e.target.value)}
                    />

                    <div className="reports-list">
                        {loading && <p className="text-muted text-sm">Loading reports…</p>}
                        {!loading && filteredReports.length === 0 && (
                            <p className="text-muted text-sm">No reports match the current filter.</p>
                        )}
                        {filteredReports.map((r) => (
                            <div
                                key={r.id}
                                className="report-list-item"
                                onClick={() => navigate(`/citizen/report/${r.id}`)}
                            >
                                <div className="flex gap-sm items-start">
                                    <img
                                        src={getImageUrl(r.image_url)}
                                        alt={r.title}
                                        className="sidebar-thumb"
                                        onError={e => { e.target.onerror = null; e.target.src = 'https://via.placeholder.com/40?text=?'; }}
                                    />
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div className="flex justify-between items-start mb-xs">
                                            <h3 className="text-sm font-semibold" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 130 }}>{r.title}</h3>
                                            <Badge variant={statusVariant(r.status)} className="text-xs">
                                                {statusLabel(r.status)}
                                            </Badge>
                                        </div>
                                        {r.ai_severity_score && (
                                            <p className="text-xs text-muted">
                                                AI Score: <strong>{Math.round(r.ai_severity_score)}/100</strong>
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* ── Map ── */}
                <div className="map-container">
                    <MapContainer center={mapCenter} zoom={12} style={{ height: '100%', width: '100%' }}>
                        <TileLayer
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        />

                        <HeatmapLayer points={heatPoints} visible={showHeatmap} />
                        <LocateController
                            trigger={locateTrigger}
                            onLocated={(pos) => { setLocating(false); setUserPos(pos); }}
                            onError={(msg) => { setLocating(false); showToast(msg); }}
                        />

                        {filteredReports.map((r) => (
                            <Marker
                                key={r.id}
                                position={[r.latitude, r.longitude]}
                                icon={ICONS[r.status] || ICONS.pending}
                            >
                                <Popup minWidth={200} autoClose={false} closeOnClick={false}>
                                    <div className="map-popup">
                                        <p className="map-popup-title">{r.title}</p>
                                        <Badge variant={statusVariant(r.status)} className="text-xs mb-xs">
                                            {statusLabel(r.status)}
                                        </Badge>
                                        {r.description && (
                                            <p className="map-popup-desc">{r.description}</p>
                                        )}
                                        {r.ai_severity_score && (
                                            <p className="map-popup-score">
                                                AI Severity: <strong>{Math.round(r.ai_severity_score)}/100</strong>
                                                {' '}({r.ai_severity_level})
                                            </p>
                                        )}
                                        <Button size="sm" onClick={() => navigate(`/citizen/report/${r.id}`)}>
                                            View Details
                                        </Button>
                                    </div>
                                </Popup>
                            </Marker>
                        ))}

                        {userPos && (
                            <Circle
                                center={userPos}
                                radius={30}
                                pathOptions={{ color: '#2563eb', fillColor: '#3b82f6', fillOpacity: 0.5, weight: 2 }}
                            />
                        )}
                    </MapContainer>

                    {/* Floating controls */}
                    <div className="map-controls">
                        <button className="map-ctrl-btn" onClick={handleLocate} disabled={locating}>
                            {locating
                                ? <><span className="locate-spinner" /> Locating…</>
                                : <><LocateIcon /> Locate Me</>
                            }
                        </button>
                        <button
                            className={`map-ctrl-btn ${showHeatmap ? 'map-ctrl-btn--active' : ''}`}
                            onClick={() => setShowHeatmap(h => !h)}
                        >
                            <HeatIcon />
                            {showHeatmap ? 'Hide Heatmap' : 'Show Heatmap'}
                        </button>
                    </div>

                    {toast && <div className="map-toast">{toast}</div>}
                </div>
            </main>
        </div>
    );
};

const LocateIcon = () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
        <circle cx="12" cy="12" r="9" strokeDasharray="4 2" />
    </svg>
);

const HeatIcon = () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 2C8 2 4 6 4 10c0 5 8 12 8 12s8-7 8-12c0-4-4-8-8-8z" /><circle cx="12" cy="10" r="3" />
    </svg>
);

export default MapView;

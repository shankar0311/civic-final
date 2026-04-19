import React, { useState, useEffect } from 'react';
import { PieChart, Pie, BarChart, Bar, LineChart, Line, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import Navbar from '../../components/shared/Navbar';
import Card from '../../components/shared/Card';
import api from '../../api';

const COLORS = {
    critical: '#EF4444',
    high: '#F59E0B',
    medium: '#3B82F6',
    low: '#10B981',
    pending: '#F59E0B',
    in_progress: '#3B82F6',
    resolved: '#10B981',
    closed: '#059669'
};

const Analytics = () => {
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState({});
    const [statusDist, setStatusDist] = useState([]);
    const [priorityDist, setPriorityDist] = useState([]);
    const [timeBoundStats, setTimeBoundStats] = useState([]);
    const [heatmapData, setHeatmapData] = useState([]);

    useEffect(() => {
        fetchAnalytics();
    }, []);

    const fetchAnalytics = async () => {
        try {
            setLoading(true);

            // Fetch all analytics data
            const [summaryRes, statusRes, priorityRes, timeRes, heatmapRes] = await Promise.all([
                api.get('/analytics/summary'),
                api.get('/analytics/status-distribution'),
                api.get('/analytics/priority-distribution'),
                api.get('/analytics/time-bound-stats'),
                api.get('/analytics/heatmap-data')
            ]);

            setSummary(summaryRes.data);

            // Transform status distribution for charts
            const statusData = Object.entries(statusRes.data.status_distribution).map(([key, value]) => ({
                name: key.replace('_', ' ').toUpperCase(),
                value,
                color: COLORS[key] || '#6B7280'
            }));
            setStatusDist(statusData);

            // Transform priority distribution
            const priorityData = Object.entries(priorityRes.data.priority_distribution).map(([key, value]) => ({
                name: key.toUpperCase(),
                value,
                color: COLORS[key] || '#6B7280'
            }));
            setPriorityDist(priorityData);

            // Transform time-bound stats
            const timeData = [
                { name: '< 24 Hours', value: timeRes.data.time_bound_stats.under_24h || 0 },
                { name: '< 7 Days', value: timeRes.data.time_bound_stats.under_7d || 0 },
                { name: '< 30 Days', value: timeRes.data.time_bound_stats.under_30d || 0 },
                { name: '> 30 Days', value: timeRes.data.time_bound_stats.over_30d || 0 }
            ];
            setTimeBoundStats(timeData);

            setHeatmapData(heatmapRes.data.heatmap_data || []);
        } catch (err) {
            console.error('Error fetching analytics:', err);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <div className="container py-lg text-center">
                    <p>Loading analytics...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            <main className="container py-lg">
                <div className="mb-lg">
                    <h1 className="text-2xl mb-xs">Analytics Dashboard</h1>
                    <p className="text-muted">Comprehensive insights for road-report operations</p>
                </div>

                {/* Summary Stats */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-md mb-lg">
                    <Card style={{ padding: '1.5rem' }}>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted">Total Reports</p>
                                <p className="text-3xl font-bold">{summary.total_reports || 0}</p>
                            </div>
                            <TrendingUp size={32} color="#3B82F6" />
                        </div>
                    </Card>

                    <Card style={{ padding: '1.5rem' }}>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted">Pending</p>
                                <p className="text-3xl font-bold text-orange-500">{summary.pending_reports || 0}</p>
                            </div>
                            <Clock size={32} color="#F59E0B" />
                        </div>
                    </Card>

                    <Card style={{ padding: '1.5rem' }}>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted">Resolved</p>
                                <p className="text-3xl font-bold text-green-600">{summary.resolved_reports || 0}</p>
                            </div>
                            <CheckCircle size={32} color="#10B981" />
                        </div>
                    </Card>

                    <Card style={{ padding: '1.5rem' }}>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted">Critical</p>
                                <p className="text-3xl font-bold text-red-600">{summary.critical_reports || 0}</p>
                            </div>
                            <AlertCircle size={32} color="#EF4444" />
                        </div>
                    </Card>
                </div>

                {/* Resolution Rate */}
                <Card style={{ padding: '1.5rem', marginBottom: '2rem' }}>
                    <h3 className="font-semibold mb-sm">Resolution Rate</h3>
                    <div className="flex items-center gap-md">
                        <div style={{
                            width: '100%',
                            height: '20px',
                            backgroundColor: '#E5E7EB',
                            borderRadius: '10px',
                            overflow: 'hidden'
                        }}>
                            <div style={{
                                width: `${summary.resolution_rate || 0}%`,
                                height: '100%',
                                backgroundColor: '#10B981',
                                transition: 'width 0.3s ease'
                            }} />
                        </div>
                        <span className="font-bold text-lg">{Math.round(summary.resolution_rate || 0)}%</span>
                    </div>
                </Card>

                {/* Charts Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg mb-lg">
                    {/* Status Distribution */}
                    <Card style={{ padding: '1.5rem' }}>
                        <h3 className="font-semibold mb-md">Status Distribution</h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                                <Pie
                                    data={statusDist}
                                    cx="50%"
                                    cy="50%"
                                    labelLine={false}
                                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                                    outerRadius={80}
                                    fill="#8884d8"
                                    dataKey="value"
                                >
                                    {statusDist.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    </Card>

                    {/* Priority Distribution */}
                    <Card style={{ padding: '1.5rem' }}>
                        <h3 className="font-semibold mb-md">Priority Distribution</h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={priorityDist}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="name" />
                                <YAxis />
                                <Tooltip />
                                <Bar dataKey="value" fill="#3B82F6">
                                    {priorityDist.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </Card>
                </div>

                {/* Time-Bound Resolution Stats */}
                <Card style={{ padding: '1.5rem', marginBottom: '2rem' }}>
                    <h3 className="font-semibold mb-md">Resolution Time Distribution</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={timeBoundStats}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" />
                            <YAxis />
                            <Tooltip />
                            <Legend />
                            <Bar dataKey="value" fill="#3B82F6" name="Reports Resolved" />
                        </BarChart>
                    </ResponsiveContainer>
                </Card>

                {/* Heatmap Data Table */}
                <Card style={{ padding: '1.5rem' }}>
                    <h3 className="font-semibold mb-md">Geographic Hotspots</h3>
                    <p className="text-sm text-muted mb-md">Top locations by report density</p>
                    <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead style={{ position: 'sticky', top: 0, backgroundColor: 'white' }}>
                                <tr style={{ borderBottom: '2px solid #E5E7EB' }}>
                                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>Location</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>Reports</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>Priority</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {heatmapData.slice(0, 10).map((point, index) => (
                                    <tr key={index} style={{ borderBottom: '1px solid #E5E7EB' }}>
                                        <td style={{ padding: '0.75rem' }}>
                                            {point.latitude.toFixed(4)}, {point.longitude.toFixed(4)}
                                        </td>
                                        <td style={{ padding: '0.75rem', fontWeight: '600' }}>
                                            {point.intensity}
                                        </td>
                                        <td style={{ padding: '0.75rem' }}>
                                            <span style={{
                                                padding: '0.25rem 0.5rem',
                                                borderRadius: '0.25rem',
                                                backgroundColor: COLORS[point.priority],
                                                color: 'white',
                                                fontSize: '0.75rem',
                                                fontWeight: '600'
                                            }}>
                                                {point.priority}
                                            </span>
                                        </td>
                                        <td style={{ padding: '0.75rem' }}>{point.status}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            </main>
        </div>
    );
};

export default Analytics;

import React, { useState, useEffect } from 'react';
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, Users, FileText, CheckCircle2 } from 'lucide-react';
import Navbar from '../../components/shared/Navbar';
import Card from '../../components/shared/Card';
import api from '../../api';
import './AdminDashboard.css';

const COLORS = ['#0F766E', '#F59E0B', '#EF4444', '#3B82F6', '#10B981'];

const AdminDashboard = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.get('/analytics/dashboard')
            .then(({ data }) => setStats(data))
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const categoryData = stats?.severity_dist ?? [];
    const monthlyData  = stats?.monthly_trends ?? [];

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            <main className="container py-lg">
                <div className="dashboard-header">
                    <h1 className="text-2xl mb-xs">Admin Dashboard</h1>
                    <p className="text-muted">System overview and analytics</p>
                </div>

                <div className="admin-stats-grid">
                    <Card className="admin-stat-card">
                        <div className="admin-stat-icon reports">
                            <FileText size={24} />
                        </div>
                        <div className="admin-stat-content">
                            <p className="admin-stat-label">Total Reports</p>
                            <p className="admin-stat-value">{loading ? '—' : stats?.total_reports ?? 0}</p>
                            <p className="admin-stat-trend positive">
                                <TrendingUp size={14} /> Live data
                            </p>
                        </div>
                    </Card>

                    <Card className="admin-stat-card">
                        <div className="admin-stat-icon users">
                            <Users size={24} />
                        </div>
                        <div className="admin-stat-content">
                            <p className="admin-stat-label">Active Users</p>
                            <p className="admin-stat-value">{loading ? '—' : stats?.active_users ?? 0}</p>
                            <p className="admin-stat-trend positive">
                                <TrendingUp size={14} /> Registered citizens
                            </p>
                        </div>
                    </Card>

                    <Card className="admin-stat-card">
                        <div className="admin-stat-icon resolved">
                            <CheckCircle2 size={24} />
                        </div>
                        <div className="admin-stat-content">
                            <p className="admin-stat-label">Resolved Reports</p>
                            <p className="admin-stat-value">{loading ? '—' : stats?.resolved_reports ?? 0}</p>
                            <p className="admin-stat-trend positive">
                                <TrendingUp size={14} /> Live data
                            </p>
                        </div>
                    </Card>

                    <Card className="admin-stat-card">
                        <div className="admin-stat-icon rate">
                            <TrendingUp size={24} />
                        </div>
                        <div className="admin-stat-content">
                            <p className="admin-stat-label">Resolution Rate</p>
                            <p className="admin-stat-value">{loading ? '—' : `${stats?.resolution_rate ?? 0}%`}</p>
                            <p className="admin-stat-trend positive">
                                <TrendingUp size={14} /> Live data
                            </p>
                        </div>
                    </Card>
                </div>

                <div className="charts-grid">
                    <Card>
                        <h3 className="text-lg mb-md">Severity Distribution</h3>
                        {categoryData.length === 0 && !loading
                            ? <p className="text-muted text-sm">No AI-analyzed reports yet.</p>
                            : (
                            <ResponsiveContainer width="100%" height={300}>
                                <PieChart>
                                    <Pie
                                        data={categoryData}
                                        cx="50%"
                                        cy="50%"
                                        labelLine={false}
                                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                        outerRadius={80}
                                        dataKey="value"
                                    >
                                        {categoryData.map((_, index) => (
                                            <Cell key={index} fill={COLORS[index % COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        )}
                    </Card>

                    <Card>
                        <h3 className="text-lg mb-md">Monthly Trends</h3>
                        {monthlyData.length === 0 && !loading
                            ? <p className="text-muted text-sm">No data for the last 6 months.</p>
                            : (
                            <ResponsiveContainer width="100%" height={300}>
                                <BarChart data={monthlyData}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="month" />
                                    <YAxis />
                                    <Tooltip />
                                    <Legend />
                                    <Bar dataKey="reports"  fill="#0F766E" name="Total Reports" />
                                    <Bar dataKey="resolved" fill="#10B981" name="Resolved" />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </Card>
                </div>
            </main>
        </div>
    );
};

export default AdminDashboard;

import React, { useEffect, useState } from 'react';
import api from '../api';

function ReportList() {
    const [reports, setReports] = useState([]);

    useEffect(() => {
        const fetchReports = async () => {
            try {
                const response = await api.get('/reports/');
                setReports(Array.isArray(response.data) ? response.data : response.data.items || []);
            } catch (error) {
                console.error('Error fetching reports:', error);
            }
        };
        fetchReports();
    }, []);

    return (
        <div>
            <h2 className="text-2xl font-bold mb-4">Recent Reports</h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {reports.map((report) => (
                    <div key={report.id} className="bg-white p-4 rounded shadow">
                        <h3 className="font-bold text-lg">{report.title}</h3>
                        <p className="text-gray-600 text-sm mb-2">
                            {report.category} • {report.status} • <span className={`font-semibold ${report.severity === 'critical' ? 'text-red-600' : report.severity === 'high' ? 'text-orange-500' : 'text-blue-500'}`}>{report.severity}</span>
                        </p>
                        <p className="mb-2">{report.description}</p>
                        <div className="text-xs text-gray-500">
                            Upvotes: {report.upvotes}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default ReportList;

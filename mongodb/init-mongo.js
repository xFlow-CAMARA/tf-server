// MongoDB initialization script for TF-SDK API
// Creates collections and indexes for API usage and metrics

db.createCollection('api_usage_logs');
db.createCollection('api_metrics_hourly');
db.createCollection('qod_sessions');
db.createCollection('traffic_influence_subscriptions');
db.createCollection('location_queries');
db.createCollection('device_status_queries');
db.createCollection('number_verification_checks');
db.createCollection('sim_swap_checks');
db.createCollection('ue_profiles');

db.api_usage_logs.createIndex({ timestamp: -1 });
db.api_metrics_hourly.createIndex({ hour: -1 });
db.qod_sessions.createIndex({ timestamp: -1 });
db.traffic_influence_subscriptions.createIndex({ timestamp: -1 });
db.location_queries.createIndex({ timestamp: -1 });
db.device_status_queries.createIndex({ timestamp: -1 });
db.number_verification_checks.createIndex({ timestamp: -1 });
db.sim_swap_checks.createIndex({ timestamp: -1 });
db.ue_profiles.createIndex({ timestamp: -1 });

print('MongoDB collections and indexes created for TF-SDK API');

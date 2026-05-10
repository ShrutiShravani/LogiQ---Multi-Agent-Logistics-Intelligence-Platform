import mlflow
import numpy as np
from typing import List
from src.models.data_models import ShipmentModel


def log_individual_shipment(shipment: ShipmentModel):
    """Logs granular metrics for a single shipment to MLflow."""
    # Prefixing with 'shipment_id' to keep the MLflow UI organized
    prefix = f"shipment_{shipment.shipment_id}"
    
    metrics = {
        # Guardrail Metrics
        f"{prefix}_gr_latency": shipment.guardrail_latency,
        f"{prefix}_gr_cost": shipment.guardrail_cost_usd,
        f"{prefix}_gr_tokens": shipment.guardrail_prompt_tokens + shipment.guardrail_completion_tokens,  
        f"{prefix}_gr_safe": 1 if shipment.guardrail_is_safe else 0,

        
        # Extraction Metrics
        f"{prefix}_doc_latency": shipment.doc_latency,
        f"{prefix}_doc_cost": shipment.doc_llm_cost_usd,
        f"{prefix}_doc_tokens": shipment.doc_prompt_tokens + shipment.doc_completion_tokens,
        f"{prefix}_doc_ttft":shipment.doc_ttft,
        
        # Validation & Pricing
        f"{prefix}_val_latency": shipment.validation_latency,
        f"{prefix}_val_tokens": shipment.validation_prompt_tokens+ shipment.validation_completion_tokens,
        f"{prefix}_val_cost": shipment.validation_llm_cost_usd,
        
        f"{prefix}_routing_latency": shipment.route_agent_latency,

        f"{prefix}_pricing_latency": shipment.pricing_agent_latency,

        f"{prefix}_critic_latency": shipment.critic_agent_latency,
        
        # ROI & Savings
        f"{prefix}_savings": shipment.margin_savings,
        f"{prefix}_opt_ratio": shipment.optimization_ratio,
        f"{prefix}_is_anomaly": 1 if shipment.is_anomaly else 0
    }
    mlflow.log_metrics(metrics)

def log_batch_summary(all_shipments: List[ShipmentModel],client: mlflow.tracking.MlflowClient, run_id: str):
    """Calculates and logs P95, P96, P99 and totals for the entire run."""
    
    # 1. Collect distributions for Percentiles
    g_latencies = [s.guardrail_latency for s in all_shipments]
    doc_latencies = [s.doc_latency for s in all_shipments]
    val_latencies = [s.validation_latency for s in all_shipments]
    pricing_latencies = [s.pricing_agent_latency for s in all_shipments]
    route_latencies=[s.route_agent_latency for s in all_shipments]
    critic_latencies= [s.critic_agent_latency for s in all_shipments]

   
    # 2. Economic Totals
    total_savings = sum([s.margin_savings for s in all_shipments])
    total_batch_cost = sum([
        s.guardrail_cost_usd + s.doc_llm_cost_usd + s.validation_llm_cost_usd 
        for s in all_shipments
    ])

    # 3. Aggregated Batch Metrics
    summary_metrics = {
        # Guardrail Percentiles
        "guardrail_p95": np.percentile(g_latencies, 95),
        "guardrail_p96": np.percentile(g_latencies, 96),
        "guardrail_p99": np.percentile(g_latencies, 99),
        "guardrail_avg_tokens": np.mean([s.guardrail_prompt_tokens for s in all_shipments]),
        
        # Extraction & Validation Percentiles
        "doc_extraction_p95": np.percentile(doc_latencies, 95),
        "doc_extraction_p96": np.percentile(doc_latencies, 96),
        "doc_extraction_p99": np.percentile(doc_latencies, 99),

        "validation_p95": np.percentile(val_latencies, 95),
        "validation_p96": np.percentile(val_latencies, 96),
        "validation_p99": np.percentile(val_latencies, 99),

        "route_agent":np.percentile(route_latencies,95),
        "route_agent_p96":np.percentile(route_latencies,96),
        "route_agent_p99":np.percentile(route_latencies,99),

        "pricing_p95": np.percentile(pricing_latencies, 95),
        "pricing_p96": np.percentile(pricing_latencies, 96),
        "pricing_p99": np.percentile(pricing_latencies, 99),
        
        "critic_p95": np.percentile(critic_latencies, 95),
        "critic_p96": np.percentile(critic_latencies, 96),
        "critic_p99": np.percentile(critic_latencies, 99),

        
        # System Health
        "total_batch_savings_usd": round(total_savings, 2),
        "total_llm_spend_usd": round(total_batch_cost, 4),
        "avg_optimization_ratio": np.mean([s.optimization_ratio for s in all_shipments]),
        "total_overrides": sum([s.critic_override_count for s in all_shipments]),
        "batch_success_rate": np.mean([1 if s.is_verified and not s.is_anomaly else 0 for s in all_shipments]),
       
    }
    
    for key,value in summary_metrics.items():
        client.log_metric(run_id, key, value)
    
    # Log the Agent Trace as a Text Artifact for the last shipment (to see the thought process)
    with open("latest_agent_trace.txt", "w") as f:
        f.write("\n".join(all_shipments[-1].agent_trace))
    mlflow.log_artifact("latest_agent_trace.txt")

    print(f" Batch Audit Complete. Total Saved: ${total_savings} | P99 Latency: {summary_metrics['guardrail_p99']:.2f}s")
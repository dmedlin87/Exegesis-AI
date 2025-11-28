"use client";

import React, { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import type { DiscoveryType } from "../types";
import styles from "./DiscoveryGalaxy.module.css";

interface GraphNode {
  id: string;
  type: "discovery" | "evidence";
  label: string;
  discoveryType?: DiscoveryType;
  confidence?: number;
  viewed?: boolean;
  // D3 simulation properties
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface DiscoveryGalaxyProps {
  filter?: DiscoveryType | "all";
  viewedOnly?: boolean;
}

const DISCOVERY_COLORS: Record<string, string> = {
  pattern: "#3b82f6",      // blue
  contradiction: "#f97316", // orange
  gap: "#a855f7",          // purple
  connection: "#10b981",   // green
  trend: "#14b8a6",        // teal
  anomaly: "#ef4444",      // red
  evidence: "#94a3b8",     // gray
};

export function DiscoveryGalaxy({ filter = "all", viewedOnly = false }: DiscoveryGalaxyProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadGraphData();
  }, [filter, viewedOnly]);

  useEffect(() => {
    if (graphData && svgRef.current && containerRef.current) {
      renderGraph(graphData);
    }
  }, [graphData]);

  const loadGraphData = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (filter && filter !== "all") {
        params.append("discovery_type", filter);
      }
      if (viewedOnly) {
        params.append("viewed", "true");
      }

      const response = await fetch(`/api/discoveries/graph?${params.toString()}`);
      if (!response.ok) {
        throw new Error("Failed to load graph data");
      }

      const data: GraphData = await response.json();
      setGraphData(data);
    } catch (err) {
      console.error("Error loading graph:", err);
      setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  };

  const renderGraph = (data: GraphData) => {
    if (!svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Clear previous content
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current)
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height]);

    // Create a group for zoom/pan
    const g = svg.append("g");

    // Set up zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Create force simulation
    const simulation = d3.forceSimulation<GraphNode>(data.nodes)
      .force("link", d3.forceLink<GraphNode, GraphLink>(data.links)
        .id((d) => d.id)
        .distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(30));

    // Create arrow markers for directed links
    const defs = g.append("defs");

    const arrowMarker = defs.append("marker")
      .attr("id", "arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto");

    arrowMarker.append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#64748b");

    // Draw links
    const link = g.append("g")
      .attr("class", "links")
      .selectAll<SVGLineElement, GraphLink>("line")
      .data(data.links)
      .join("line")
      .attr("stroke", (d) => {
        if (d.type === "contradicts") return DISCOVERY_COLORS.contradiction;
        if (d.type === "connects") return DISCOVERY_COLORS.connection;
        return "#64748b";
      })
      .attr("stroke-width", 2)
      .attr("stroke-opacity", 0.6)
      .attr("marker-end", "url(#arrow)");

    // Draw nodes
    const node = g.append("g")
      .attr("class", "nodes")
      .selectAll<SVGGElement, GraphNode>("g")
      .data(data.nodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(d3.drag<SVGGElement, GraphNode>()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));

    // Add circles for nodes
    node.append("circle")
      .attr("r", (d) => d.type === "discovery" ? 15 : 8)
      .attr("fill", (d) => {
        if (d.type === "evidence") return DISCOVERY_COLORS.evidence;
        return DISCOVERY_COLORS[d.discoveryType || "pattern"];
      })
      .attr("stroke", (d) => d.viewed === false ? "#fbbf24" : "#fff")
      .attr("stroke-width", (d) => d.viewed === false ? 3 : 2)
      .attr("opacity", (d) => d.viewed === false ? 1 : 0.8);

    // Add labels for discovery nodes
    node.filter((d) => d.type === "discovery")
      .append("text")
      .attr("dx", 20)
      .attr("dy", 5)
      .attr("font-size", "12px")
      .attr("font-weight", "500")
      .attr("fill", "#1e293b")
      .text((d) => {
        const maxLen = 30;
        return d.label.length > maxLen ? d.label.substring(0, maxLen) + "..." : d.label;
      });

    // Add confidence indicator for discoveries
    node.filter((d) => d.type === "discovery" && d.confidence !== undefined)
      .append("circle")
      .attr("r", 5)
      .attr("cx", 15)
      .attr("cy", -15)
      .attr("fill", (d) => {
        const conf = d.confidence || 0;
        if (conf > 0.8) return "#10b981";
        if (conf > 0.5) return "#fbbf24";
        return "#ef4444";
      })
      .attr("stroke", "#fff")
      .attr("stroke-width", 1);

    // Node click handler
    node.on("click", (event, d) => {
      event.stopPropagation();
      setSelectedNode(d);

      // Highlight connected nodes
      const connectedNodeIds = new Set<string>();
      connectedNodeIds.add(d.id);

      data.links.forEach((link) => {
        const sourceId = typeof link.source === "string" ? link.source : link.source.id;
        const targetId = typeof link.target === "string" ? link.target : link.target.id;

        if (sourceId === d.id) connectedNodeIds.add(targetId);
        if (targetId === d.id) connectedNodeIds.add(sourceId);
      });

      node.attr("opacity", (n) => connectedNodeIds.has(n.id) ? 1 : 0.2);
      link.attr("opacity", (l) => {
        const sourceId = typeof l.source === "string" ? l.source : l.source.id;
        const targetId = typeof l.target === "string" ? l.target : l.target.id;
        return sourceId === d.id || targetId === d.id ? 0.8 : 0.1;
      });
    });

    // Clear selection on background click
    svg.on("click", () => {
      setSelectedNode(null);
      node.attr("opacity", 1);
      link.attr("opacity", 0.6);
    });

    // Update positions on simulation tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (typeof d.source === "string" ? 0 : d.source.x || 0))
        .attr("y1", (d) => (typeof d.source === "string" ? 0 : d.source.y || 0))
        .attr("x2", (d) => (typeof d.target === "string" ? 0 : d.target.x || 0))
        .attr("y2", (d) => (typeof d.target === "string" ? 0 : d.target.y || 0));

      node.attr("transform", (d) => `translate(${d.x || 0},${d.y || 0})`);
    });
  };

  const handleNodeAction = (nodeId: string) => {
    if (!graphData) return;

    const node = graphData.nodes.find((n) => n.id === nodeId);
    if (!node) return;

    if (node.type === "discovery") {
      // Mark as viewed and navigate
      fetch(`/api/discoveries/${nodeId}/view`, { method: "POST" }).catch(console.error);
      window.location.href = `/discoveries`;
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading galaxy view...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          <p>Failed to load graph: {error}</p>
          <button onClick={loadGraphData} className={styles.retryButton}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.empty}>
          <p>No discoveries to visualize</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container} ref={containerRef}>
      <svg ref={svgRef} className={styles.svg} />

      {selectedNode && (
        <div className={styles.nodeInfo}>
          <div className={styles.nodeInfoHeader}>
            <h3>{selectedNode.label}</h3>
            <button
              onClick={() => setSelectedNode(null)}
              className={styles.closeButton}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div className={styles.nodeInfoBody}>
            <p>
              <strong>Type:</strong> {selectedNode.type}
            </p>
            {selectedNode.discoveryType && (
              <p>
                <strong>Category:</strong> {selectedNode.discoveryType}
              </p>
            )}
            {selectedNode.confidence !== undefined && (
              <p>
                <strong>Confidence:</strong> {Math.round(selectedNode.confidence * 100)}%
              </p>
            )}
            {selectedNode.type === "discovery" && (
              <button
                onClick={() => handleNodeAction(selectedNode.id)}
                className={styles.exploreButton}
              >
                Explore →
              </button>
            )}
          </div>
        </div>
      )}

      <div className={styles.legend}>
        <h4>Legend</h4>
        <div className={styles.legendItems}>
          <div className={styles.legendItem}>
            <div className={styles.legendColor} style={{ backgroundColor: DISCOVERY_COLORS.anomaly }} />
            <span>Anomaly</span>
          </div>
          <div className={styles.legendItem}>
            <div className={styles.legendColor} style={{ backgroundColor: DISCOVERY_COLORS.contradiction }} />
            <span>Contradiction</span>
          </div>
          <div className={styles.legendItem}>
            <div className={styles.legendColor} style={{ backgroundColor: DISCOVERY_COLORS.gap }} />
            <span>Gap</span>
          </div>
          <div className={styles.legendItem}>
            <div className={styles.legendColor} style={{ backgroundColor: DISCOVERY_COLORS.connection }} />
            <span>Connection</span>
          </div>
          <div className={styles.legendItem}>
            <div className={styles.legendColor} style={{ backgroundColor: DISCOVERY_COLORS.pattern }} />
            <span>Pattern</span>
          </div>
          <div className={styles.legendItem}>
            <div className={styles.legendColor} style={{ backgroundColor: DISCOVERY_COLORS.trend }} />
            <span>Trend</span>
          </div>
          <div className={styles.legendItem}>
            <div className={styles.legendColor} style={{ backgroundColor: DISCOVERY_COLORS.evidence }} />
            <span>Evidence</span>
          </div>
        </div>
        <div className={styles.legendHint}>
          💡 Drag nodes to rearrange • Scroll to zoom • Click node for details
        </div>
      </div>
    </div>
  );
}

/*!
 * Copyright (C) 2015 Red Hat Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

var nodeLabelOffset = { x:6, y:3 };
var diagonal = d3.svg.diagonal().projection(function(d) { return [ d.y, d.x ]; });
var dragging = false;
var tree = d3.layout.tree()
    .nodeSize([16, 200])
    .children(function(d) { return d.children; })
    .sort(function(a, b) { return d3.ascending(a.name, b.name); });

/* The PSTree class lays out a set of SVG selements to show a tree of processes
 * on a machine, similar to the pstree command.
 */
function PSTree(svg) {
  this.group = svg.append("g");
  this.linkGroup = this.group.append("g");
  this.nodeGroup = this.group.append("g");

  /* Allow the user to pan the SVG and view processes that are currently
   * off-screen. */
  var zoom = d3.behavior.zoom()
      .scaleExtent([1, 1])
      .on("zoom", function() {
          this.group.attr("transform", "translate(" + d3.event.translate + ") scale(" + d3.event.scale + ")");
      }.bind(this));

  svg.call(zoom);

  this.drag = d3.behavior.drag()
      .on("dragstart", function(d) {
        dragging = true;
        d3.event.sourceEvent.stopPropagation();

        this["origin-x"] = d3.event.sourceEvent.pageX;
        this["origin-y"] = d3.event.sourceEvent.pageY;
        this["ghost-x"] = d3.event.sourceEvent.pageX;
        this["ghost-y"] = d3.event.sourceEvent.pageY;

        /* When a node is dragged, crated a new "ghost" node with the same text
         * for the user to drag around. */
        d3.select("body")
            .append("div")
            .text(d.name + " (" + d.id + ")")
            .classed("ghost", true)
            .style({
                "opacity" : 0,
                "position" : "absolute",
                "left" : this["ghost-x"] + "px",
                "top" : this["ghost-y"] + "px",
                "pointer-events": "none",
            })
            .transition()
            .duration(250)
            .style("opacity", 1.0);

        d3.select(this).classed("dragging-node", true);
      })
      .on("drag", function(d) {
        this["ghost-x"] += d3.event.dx;
        this["ghost-y"] += d3.event.dy;

        /* Move the ghost node as the user drags. */
        d3.select(".ghost").style({
            left: this["ghost-x"] + "px",
            top: this["ghost-y"] + "px"
        });

        /* Show a dragging cursor if we're dragging over another process tree,
         * or a "not allowed" cursor for anything else.  Processes can be
         * dragged onto process trees. */
        var target = d3.select(".pstree:hover");
        if (target.node() && target.datum() != svg.datum()) {
          target.selectAll("*").style("cursor", "copy");
        } else {
          d3.selectAll("body").style("cursor", "not-allowed");
        }
      })
      .on("dragend", function() {
        dragging = false;

        var target = d3.select(".pstree:hover");

        if (target.node() && target.datum() != svg.datum()) {
          /* If the node was dragged onto a different process tree, migrate the
           * node to that machine. */
          d3.select(".ghost")
              .style("transform", "scale(1.0)")
              .transition()
              .duration(250)
              .ease("cubic-out")
              .style("opacity", 0)
              .style("transform", "scale(0.75)")
              .remove();

          migrate(d3.select(this).datum(), svg.datum(), target.datum());
        } else {
          /* If the drag was cancelled, move the ghost node back to its
           * original position and remove it. */
          d3.select(".ghost")
              .transition()
              .duration(500)
              .ease("cubic-out")
              .style({
                  "left" : this["origin-x"] + "px",
                  "top" : this["origin-y"] + "px",
                  "opacity" : 0,
              })
              .remove();
        }

        d3.selectAll("body,.pstree *").style("cursor", undefined);
        d3.select(this).classed({"active-node" : false, "dragging-node" : false});
      });
}


/* Wait for server-sent events containing the process data and redraw the tree
 * whenever new data arrives. */
PSTree.prototype.listen = function(address) {
  new EventSource(address + "/procs")
      .addEventListener("procs", PSTree.prototype.redraw.bind(this));
};


/* This is an event listener for EventSource that adds and removes nodes in the
 * tree as necessary when new proccess data is available.
 */
PSTree.prototype.redraw = function(e) {
  var data = JSON.parse(e.data);

  /* Update the nodes with the latest data. A node is created for every
   * process on the system, and they're arrange in a tree that shows
   * parent/child processes. */
  var nodeData = tree.nodes(data);
  var nodes = this.nodeGroup.selectAll("g.node").data(nodeData, function(d) { return d.id; });

  /* Nodes are drawn as an SVG group containing a circle and a text label,
   * which indicates the name of the process.  */
  var nodeGroups = nodes.enter()
      .append("g")
      .attr("class", "node")
      .attr("transform", function(d) { return "translate(" + d.y + "," + d.x + ")"; })
      .style("opacity", 0)
      .call(this.drag)
      .on("mouseover", function(d) {
        if (dragging) return;

        /* Highlight the text. */
        d3.select(this).classed("active-node", true);
        d3.select(this).select("text.node-label").text(function(d) { return d.name; });

        /* Show more detailed information about this process when it's hovered
         * over. */
        d3.select("#process-name").text(d.name);
        d3.select("#process-id").text(d.id);
        if (d.children) {
          d3.select("#process-children")
              .text(d.children.map(function(d) { return d.name; }).join(", "));
        } else {
          d3.select("#process-children").text("none");
        }
      })
      .on("mouseout", function(d) {
        /* Change the text back to normal. */
        d3.select(this).classed("active-node", false);
        d3.select(this).select("text.node-label").text(function(d) { return d.name; });
      });

  nodeGroups.append("circle").attr({r: 3.0});
  nodeGroups.append("text")
      .attr(nodeLabelOffset)
      .classed("node-label", true);

  nodes
      .transition()
      .duration(200)
      .attr("transform", function(d) { return "translate(" + d.y + "," + d.x + ")"; })
      .style("opacity", 1);

  nodes.each(function () { d3.select(this).select("text.node-label").text(); });
  this.nodeGroup.selectAll("text.node-label").text(function(d) { return d.name; });

  nodes.exit()
      .transition()
      .duration(200)
      .style("opacity", 0)
      .remove();

  /* Update the links between the nodes with the latest data. */
  var linkData = tree.links(nodeData);
  var links = this.linkGroup.selectAll("path.link").data(linkData, function(d) { return d.target.id; });

  /* Links are drawn as SVG paths using d3's svg.diagonal helper. */
  links.enter()
      .append("path")
      .attr("class", "link")
      .style("opacity", 0);

  links
      .transition()
      .duration(200)
      .attr("d", diagonal)
      .style("opacity", 1);

  links.exit()
      .transition()
      .duration(200)
      .style("opacity", 0)
      .remove();
};

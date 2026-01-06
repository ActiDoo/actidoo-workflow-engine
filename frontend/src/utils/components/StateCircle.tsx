// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from "react";

interface StateCircle {
  taskId: string;
  number: number;
  color: string;
  state: "success" | "error";
}

export const StateCircle: React.FC<StateCircle> = props => {
  return (
    <div
      id={`${props.taskId}-${props.state}`}
      style={{ backgroundColor: props.color, borderRadius: "25%", width: 25 }}
    >
      <p>{props.number}</p>
    </div>
  );
}


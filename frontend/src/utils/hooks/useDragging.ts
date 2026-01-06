// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { DragEvent, useState } from 'react';

export const useDragging = (
  onDrop: (data: DragEvent<HTMLDivElement>) => void
): [
  boolean,
  (event: DragEvent<HTMLDivElement>) => void,
  (event: DragEvent<HTMLDivElement>) => void,
  (event: DragEvent<HTMLDivElement>) => void
] => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragging(false);
    onDrop(event);
  };
  return [isDragging, handleDragOver, handleDragLeave, handleDrop];
};

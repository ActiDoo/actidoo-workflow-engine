import { UiAction, UiActionType, UiState } from '@/store/ui/setup';

const initState: UiState = {
  loading: {},
  toast: undefined,
  dialog: undefined,
};

export default (state = initState, action: UiAction): UiState => {
  switch (action.type) {
    case UiActionType.SET_LOADING:
      return {
        ...state,
        loading: {
          ...state.loading,
          [action.payload.id]: action.payload.loading,
        },
      };
    case UiActionType.ADD_TOAST:
      return {
        ...state,
        toast: action.payload.content,
      };
    case UiActionType.SET_DIALOG:
      return {
        ...state,
        dialog: action.payload?.props,
      };
    default:
      return state;
  }
};

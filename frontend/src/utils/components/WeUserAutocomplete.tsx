import React, { useEffect, useRef } from 'react';
import { Input, InputDomRef, SuggestionItem, Ui5CustomEvent } from '@ui5/webcomponents-react';
import { useDispatch, useSelector } from 'react-redux';
import Suggestions from '@ui5/webcomponents/dist/features/InputSuggestions.js';
import { postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import { State } from '@/store';
import { InputSuggestionItemSelectEventDetail } from '@ui5/webcomponents/dist/Input';

interface AdminUserAutocompleteProps {
  initialLabel?: string;
  onSelectUser?: (userId: string | undefined) => void;
}

const WeUserAutocomplete: React.FC<AdminUserAutocompleteProps> = props => {
  const inputEl = useRef<InputDomRef>(null);

  const dispatch = useDispatch();

  const searchWfUsers =
    useSelector((state: State) => state.data[WeDataKey.ADMIN_SEARCH_WF_USERS])?.data?.options ?? [];

  useEffect(() => {
    void Suggestions.init();
    fetchUserData();
  }, []);

  const fetchUserData = (): void => {
    dispatch(
      postRequest(WeDataKey.ADMIN_SEARCH_WF_USERS, {
        search: inputEl.current?.value?.replaceAll('(', '').replaceAll(')', '') ?? '',
        include_value: '',
      })
    );
  };

  return (
    <>
      <Input
        className="w-full w-96"
        ref={inputEl}
        placeholder="Search User"
        value={props.initialLabel ?? ''}
        showSuggestions
        showClearIcon
        onSuggestionItemSelect={(
          event: Ui5CustomEvent<InputDomRef, InputSuggestionItemSelectEventDetail>
        ) => {
          if (props.onSelectUser && event.detail.item.dataset.value) {
            props.onSelectUser(event.detail.item.dataset.value);
          }
        }}
        onInput={() => {
          fetchUserData();
          if (props.onSelectUser) {
            props.onSelectUser(undefined);
          }
        }}>
        {searchWfUsers.map(user => {
          return (
            <SuggestionItem
              key={`suggest_user_${user.value}`}
              text={user.label}
              data-value={user.value}
            />
          );
        })}
      </Input>
    </>
  );
};
export default WeUserAutocomplete;

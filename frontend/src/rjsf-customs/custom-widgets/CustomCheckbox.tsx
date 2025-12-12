import { WidgetProps } from '@rjsf/utils';
import { ChangeEvent, ReactElement, useEffect, useState } from 'react';

const CustomCheckbox = (props: WidgetProps): ReactElement => {

  //console.log(props.value) //during first load, this component will be rendered four times with value undefined -> undefined -> false -> false

  const [isChecked, setIsChecked] = useState<boolean>(false); // do not set to props.value initially, because it can be undefined first.


  //useEffect: during every render we will assign props.value to 'isChecked'
  useEffect(() => {
    //props.value can be undefined initially, see also comment above, so we can't write only "setIsChecked(props.value)"
    if (props.value)
      setIsChecked(props.value)
    else
      setIsChecked(false)
  }, [props]);
  
  function onCheckbox(evt: ChangeEvent<HTMLInputElement>) {
    props.onChange(!isChecked)  //propagate the new value, so WidgetProps can take care of it. Afterwards a re-render will happen.
  }

  return (
    <div className="mb-0">
      <div className='flex'>
        <div>
          {/* we need a div around the input, otherwise the width of the input (the checkbox itself) will be too thin for long labels*/}
          <input className="mr form-check-input" type="checkbox" checked={isChecked} onChange={evt => onCheckbox(evt)} required={props.required} disabled={props.disabled}/> 
        </div>
        <label className={"ml-2 text-sm" + (props.disabled ? 'opacity-75' : '')}>{props.required ? props.label + "*" : props.label}</label>        
      </div>
      
      {/* That's the hint: */}
      <p className={"text-gray-500 text-xs " + (props.disabled ? 'opacity-80' : '')}>{props.options.description}</p>
    </div>
  );
};
export default CustomCheckbox;

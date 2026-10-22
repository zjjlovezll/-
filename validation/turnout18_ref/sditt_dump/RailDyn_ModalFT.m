%% 计算车轮下钢轨的位移、速度、加速度
function [Dis_Rail, Vel_Rail, Acc_Rail, DynStatus_Rail] = RailDyn_ModalFT(InpPar, Zwy, Zsd, Zjsd, ShapeFunction)

% global InpPar.Nw InpPar.N_ConPatch InpPar.N_Node InpPar.Type_Rail InpPar.ModeShape InpPar.Exp_WS InpPar.N_track

Dis_Rail = zeros(InpPar.Nw*InpPar.N_ConPatch,3+3);      % 钢轨接触点处 X、Y、Z 方向位移（列） m
Vel_Rail = zeros(InpPar.Nw*InpPar.N_ConPatch,3+3);      % 钢轨接触点处 X、Y、Z 方向（列）速度 m/s
Acc_Rail = zeros(InpPar.Nw*InpPar.N_ConPatch,3+3);      % 钢轨接触点处 X、Y、Z 方向（列）加速度 m/s^2

% 4DOF
DOF_num = 4;
DOF_pos = [2,3,5,6];

% 6DOF
% DOF_num = 6;
% DOF_pos = [1,2,3,4,5,6];

%% 获取各钢轨的动力学参数 DynStatus_Rail InpPar.N_Node
% Dyn_Track_Dis, DynStatus_Rail
for i2 = 1:1:length(InpPar.Type_Rail)
%     Dyn_Track_Dis.(InpPar.Type_Rail{i2}) = InpPar.ModeShape.(InpPar.Type_Rail{i2}) * Zwy(1:InpPar.N_track,4);
%     Dyn_Track_Vel.(InpPar.Type_Rail{i2}) = InpPar.ModeShape.(InpPar.Type_Rail{i2}) * Zsd(1:InpPar.N_track,4);
%     Dyn_Track_Acc.(InpPar.Type_Rail{i2}) = InpPar.ModeShape.(InpPar.Type_Rail{i2}) * Zjsd(1:InpPar.N_track,4);

    %%% Revision by Wang X.
    my_type = InpPar.Type_Rail{i2};
    A    = InpPar.ModeShape.(my_type);   % m×n
    N    = InpPar.N_track;
    
    M = [ Zwy(1:N,4),  Zsd(1:N,4),  Zjsd(1:N,4) ];
    R = A * M;   % → [m×3]
    
    % 拆分列，赋回结构体
    Dyn_Track_Dis.(my_type) = R(:,1);
    Dyn_Track_Vel.(my_type) = R(:,2);
    Dyn_Track_Acc.(my_type) = R(:,3);
    %%% Revision by Wang X.
    
    j_max = InpPar.N_Node.(InpPar.Type_Rail{i2});
    DynStatus_Rail.([InpPar.Type_Rail{i2},'_Dis']) = zeros(j_max,6);
    DynStatus_Rail.([InpPar.Type_Rail{i2},'_Vel']) = zeros(j_max,6);
    DynStatus_Rail.([InpPar.Type_Rail{i2},'_Acc']) = zeros(j_max,6);
    for j = 1:1:j_max
        pos = (j-1)*DOF_num+1:j*DOF_num;
        DynStatus_Rail.([InpPar.Type_Rail{i2},'_Dis'])(j,DOF_pos) = Dyn_Track_Dis.(InpPar.Type_Rail{i2})(pos,1)';
        DynStatus_Rail.([InpPar.Type_Rail{i2},'_Vel'])(j,DOF_pos) = Dyn_Track_Vel.(InpPar.Type_Rail{i2})(pos,1)';
        DynStatus_Rail.([InpPar.Type_Rail{i2},'_Acc'])(j,DOF_pos) = Dyn_Track_Acc.(InpPar.Type_Rail{i2})(pos,1)';
    end    
end


%% 获取轮下钢轨的动力学参数 Dis_Rail Vel_Rail Acc_Rail
for i1 = 1:1:InpPar.Nw         %%% 轮对数
    T1 = InpPar.Exp_WS{i1};
    for i2 = 1:1:InpPar.N_ConPatch      %%% 集总质量块数目
        T2 = InpPar.Type_Rail{i2};
        i_ConPatch = InpPar.N_ConPatch*(i1-1)+i2;        
        Target_ShapeFunction_Y = ShapeFunction.([T1,'_',T2,'_Y']);
        Target_ShapeFunction_Z = ShapeFunction.([T1,'_',T2,'_Z']);
        Target_ShapeFunction_ROTY = ShapeFunction.([T1,'_',T2,'_ROTY']);
        Target_ShapeFunction_ROTZ = ShapeFunction.([T1,'_',T2,'_ROTZ']);
        Mapping_Y = ShapeFunction.([T1,'_',T2,'_Mapping_DynStatus_Y']);
        Mapping_Z = ShapeFunction.([T1,'_',T2,'_Mapping_DynStatus_Z']);
        Mapping_ROTY = ShapeFunction.([T1,'_',T2,'_Mapping_DynStatus_ROTY']);
        Mapping_ROTZ = ShapeFunction.([T1,'_',T2,'_Mapping_DynStatus_ROTZ']);
        
        if ~isempty(Target_ShapeFunction_Y)
            Dis_Rail(i_ConPatch,2) = Target_ShapeFunction_Y * Dyn_Track_Dis.(T2)(Mapping_Y);     % 钢轨横向位移
            Dis_Rail(i_ConPatch,3) = Target_ShapeFunction_Z * Dyn_Track_Dis.(T2)(Mapping_Z);     % 钢轨垂向位移
            Dis_Rail(i_ConPatch,5) = Target_ShapeFunction_ROTY * Dyn_Track_Dis.(T2)(Mapping_ROTY);     % 钢轨ROTY
            Dis_Rail(i_ConPatch,6) = Target_ShapeFunction_ROTZ * Dyn_Track_Dis.(T2)(Mapping_ROTZ);     % 钢轨ROTZ
            
            Vel_Rail(i_ConPatch,2) = Target_ShapeFunction_Y * Dyn_Track_Vel.(T2)(Mapping_Y);     % 钢轨横向速度
            Vel_Rail(i_ConPatch,3) = Target_ShapeFunction_Z * Dyn_Track_Vel.(T2)(Mapping_Z);     % 钢轨垂向速度
            Vel_Rail(i_ConPatch,5) = Target_ShapeFunction_ROTY * Dyn_Track_Vel.(T2)(Mapping_ROTY);     % 钢轨ROTY
            Vel_Rail(i_ConPatch,6) = Target_ShapeFunction_ROTZ * Dyn_Track_Vel.(T2)(Mapping_ROTZ);     % 钢轨ROTZ
            
            Acc_Rail(i_ConPatch,2) = Target_ShapeFunction_Y * Dyn_Track_Acc.(T2)(Mapping_Y);     % 钢轨横向加速度
            Acc_Rail(i_ConPatch,3) = Target_ShapeFunction_Z * Dyn_Track_Acc.(T2)(Mapping_Z);     % 钢轨垂向加速度     
            Acc_Rail(i_ConPatch,5) = Target_ShapeFunction_ROTY * Dyn_Track_Acc.(T2)(Mapping_ROTY);     % 钢轨ROTY
            Acc_Rail(i_ConPatch,6) = Target_ShapeFunction_ROTZ * Dyn_Track_Acc.(T2)(Mapping_ROTZ);     % 钢轨ROTZ                 
        end
    end
end


%% 轮轨力对柔性轨道（模态叠加法）系统做功
function [Pxt, Pxt_Track] = WR_Force_ModalFT(InpPar, xlcs, Pxt, Pjcc, Pjch, Prhxf, Con_WS, ShapeFunction)

% global xlcs InpPar.Nw InpPar.N_ConPatch InpPar.N_track InpPar.DOF_Node
% global InpPar.Exp_WS InpPar.Type_Side InpPar.Type_Rail
% global InpPar.ModeShape

for i2 = 1:1:length(InpPar.Type_Rail)
    Pxt_Track.(InpPar.Type_Rail{i2}) = zeros(InpPar.DOF_Node.(InpPar.Type_Rail{i2}),1);
end

%% 计算 Pxt_Track (DOF_Rail*1)
% Pxt_Track = zeros(DOF_Rail_start(end,3),1);
% Pxt_Track = zeros(InpPar.N_track,1);
for i1 = 1:1:InpPar.Nw             %%% 轮对数 1-4
    if xlcs <= 3 && ~isfield(Con_WS.FF, 'Normal_Force')
        if strcmp(InpPar.VehicleDir, 'Face')
            Range_i2 = [1,2];
        elseif strcmp(InpPar.VehicleDir, 'Trail')
            Range_i2 = [1,4];
        end
        for i2 = Range_i2
            i_contact = InpPar.N_ConPatch*(i1-1)+i2;
            F_Z = -(Pjcc(i_contact,1)+Prhxf(i_contact,3));
            F_Y = -(Pjch(i_contact,1)+Prhxf(i_contact,2));
            F_X = - Prhxf(i_contact,1);
            ShapeFunction_Y = ShapeFunction.([InpPar.Exp_WS{i1},'_',InpPar.Type_Rail{i2,1},'_Y']);
            ShapeFunction_Z = ShapeFunction.([InpPar.Exp_WS{i1},'_',InpPar.Type_Rail{i2,1},'_Z']);
            row_F_Lat = ShapeFunction.([InpPar.Exp_WS{i1},'_',InpPar.Type_Rail{i2,1},'_Mapping_DynStatus_Y']);
            row_F_Ver = ShapeFunction.([InpPar.Exp_WS{i1},'_',InpPar.Type_Rail{i2,1},'_Mapping_DynStatus_Z']);
            Pxt_Track.(InpPar.Type_Rail{i2})(row_F_Lat,1) = Pxt_Track.(InpPar.Type_Rail{i2})(row_F_Lat,1) + F_Y * ShapeFunction_Y';
            Pxt_Track.(InpPar.Type_Rail{i2})(row_F_Ver,1) = Pxt_Track.(InpPar.Type_Rail{i2})(row_F_Ver,1) + F_Z * ShapeFunction_Z';
        end
    else
        Con_str = Con_WS.(InpPar.Exp_WS{i1});
        for wheelside = 1:1:2
            Normal_Force = Con_str.Normal_Force.(InpPar.Type_Side{wheelside});
            Prhxf_temp = Con_str.Prhxf_T.(InpPar.Type_Side{wheelside});
            for k = 1:1:size(Normal_Force,1)
                i2 = Normal_Force(k,4);
                F_Z = -(Normal_Force(k,3)+Prhxf_temp(k,3));
                F_Y = -(Normal_Force(k,2)+Prhxf_temp(k,2));
                F_X = - Prhxf_temp(k,1);
                ShapeFunction_Y = ShapeFunction.([InpPar.Exp_WS{i1},'_',InpPar.Type_Rail{i2,1},'_Y']);
                ShapeFunction_Z = ShapeFunction.([InpPar.Exp_WS{i1},'_',InpPar.Type_Rail{i2,1},'_Z']);
                row_F_Lat = ShapeFunction.([InpPar.Exp_WS{i1},'_',InpPar.Type_Rail{i2,1},'_Mapping_DynStatus_Y']);
                row_F_Ver = ShapeFunction.([InpPar.Exp_WS{i1},'_',InpPar.Type_Rail{i2,1},'_Mapping_DynStatus_Z']);
                Pxt_Track.(InpPar.Type_Rail{i2})(row_F_Lat,1) = Pxt_Track.(InpPar.Type_Rail{i2})(row_F_Lat,1) + F_Y * ShapeFunction_Y';
                Pxt_Track.(InpPar.Type_Rail{i2})(row_F_Ver,1) = Pxt_Track.(InpPar.Type_Rail{i2})(row_F_Ver,1) + F_Z * ShapeFunction_Z';
            end
        end
    end
end

%% 转换为 InpPar.ModeShape * Pxt_Track (InpPar.N_track*1)
% for i = 1:1:2
%     m_NM = NM_FT_start(i)+1;
%     n_NM = NM_FT_start(i+1);
%     m_DOF_Rail = DOF_Rail_start(i,3)+1;
%     n_DOF_Rail = DOF_Rail_start(i+1,3);
%     
%     InpPar.ModeShape_Rail_temp = eval(['InpPar.ModeShape.', InpPar.Type_Rail{i,3}]);
%     Pxt(m_NM:n_NM,1) = Pxt(m_NM:n_NM,1) + (InpPar.ModeShape_Rail_temp)' * Pxt_Track(m_DOF_Rail:n_DOF_Rail,1);
% end

% Pxt(1:InpPar.N_track,1) = Pxt(1:InpPar.N_track,1) + InpPar.ModeShape.FT' * Pxt_Track;
                        
for i2 = 1:1:length(InpPar.Type_Rail)
    Pxt(1:InpPar.N_track,1) = Pxt(1:InpPar.N_track,1) + InpPar.ModeShape.(InpPar.Type_Rail{i2})' * Pxt_Track.(InpPar.Type_Rail{i2});
end

